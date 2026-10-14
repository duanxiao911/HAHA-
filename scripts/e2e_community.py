"""Real-browser acceptance checks for the HAHA local community product loop."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import websockets

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "e2e" / "community"
REPORT = ARTIFACTS / "report.json"
CONSOLE_REPORT = ARTIFACTS / "console-errors.json"
WEB_BASE_URL = os.getenv("HAHA_E2E_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
DEBUG_PORT = int(os.getenv("HAHA_COMMUNITY_E2E_DEBUG_PORT", "9351"))
VIEWPORTS = [390, 768, 1024, 1280, 1440]


def find_chrome() -> Path:
    candidates = [
        os.getenv("HAHA_E2E_CHROME", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    for executable in ("google-chrome", "chromium", "chromium-browser", "msedge"):
        resolved = shutil.which(executable)
        if resolved:
            return Path(resolved)
    raise RuntimeError("Could not locate Chrome, Chromium, or Edge")


async def run(websocket_url: str) -> dict[str, Any]:
    next_id = 0
    events: list[dict[str, Any]] = []
    assertions: dict[str, bool] = {}
    viewport_results: list[dict[str, Any]] = []
    page_results: list[dict[str, Any]] = []

    async with websockets.connect(websocket_url, max_size=30_000_000) as socket:
        async def command(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            nonlocal next_id
            next_id += 1
            command_id = next_id
            await socket.send(json.dumps({"id": command_id, "method": method, "params": params or {}}))
            while True:
                message = json.loads(await asyncio.wait_for(socket.recv(), timeout=25))
                if message.get("id") == command_id:
                    if "error" in message:
                        raise RuntimeError(message["error"])
                    return message.get("result", {})
                events.append(message)

        async def evaluate(expression: str) -> Any:
            result = await command(
                "Runtime.evaluate",
                {"expression": expression, "returnByValue": True, "awaitPromise": True},
            )
            details = result.get("exceptionDetails")
            if details:
                raise RuntimeError(f"Browser evaluation failed: {details}")
            return result.get("result", {}).get("value")

        async def wait_for(fragment: str, timeout: float = 25) -> str:
            deadline = time.monotonic() + timeout
            body = ""
            while time.monotonic() < deadline:
                body = str(await evaluate("document.body?.innerText || ''"))
                if fragment in body:
                    return body
                await asyncio.sleep(0.25)
            raise TimeoutError(f"Timed out waiting for {fragment!r}; body tail: {body[-1200:]}")

        async def navigate(path: str, expected: str) -> str:
            url = f"{WEB_BASE_URL}{path}"
            await command("Page.navigate", {"url": url})
            return await wait_for(expected)

        async def click_text(text: str, selector: str = "button,a") -> bool:
            expression = f"""(() => {{
              const text={json.dumps(text)};
              const el=[...document.querySelectorAll({json.dumps(selector)})]
                .find(node=>(node.innerText||node.textContent||'').trim().includes(text) && !("disabled" in node && node.disabled));
              if(!el)return false; el.click(); return true;
            }})()"""
            return bool(await evaluate(expression))

        async def click_when_ready(text: str, selector: str = "button,a", timeout: float = 25) -> None:
            """Wait for hydrated interactive markup before clicking it.

            Next.js can paint server-rendered text before React has restored the
            local demo state and attached handlers. Retrying the lookup makes the
            acceptance test exercise the actual interactive control instead of
            racing the hydration boundary.
            """
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if await click_text(text, selector):
                    return
                await asyncio.sleep(0.25)
            raise TimeoutError(f"Timed out waiting to click {text!r}")

        async def screenshot(name: str) -> None:
            shot = await command(
                "Page.captureScreenshot",
                {"format": "png", "captureBeyondViewport": True, "fromSurface": True},
            )
            (ARTIFACTS / name).write_bytes(base64.b64decode(shot["data"]))

        await command("Runtime.enable")
        await command("Page.enable")
        await command("Log.enable")
        await command("Network.enable")

        for width in VIEWPORTS:
            height = 844 if width <= 390 else 900
            await command(
                "Emulation.setDeviceMetricsOverride",
                {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width <= 768},
            )
            body = await navigate("/", "让手艺继续发生")
            metrics = await evaluate("""(() => ({
              viewport: window.innerWidth,
              scrollWidth: document.documentElement.scrollWidth,
              overflow: Math.max(0, document.documentElement.scrollWidth-window.innerWidth),
              mobileNav: getComputedStyle(document.querySelector('.productMobileNav')).display,
              cards: document.querySelectorAll('.contentCard').length,
              trustBadges: document.querySelectorAll('.productTrustBadge').length
            }))()""")
            checks = {
                "brand": "HAHA CULTURE COMMUNITY" in body,
                "feed": "内容 Feed" in body,
                "cards": metrics["cards"] >= 5,
                "trust": metrics["trustBadges"] >= 1,
                "no_horizontal_overflow": metrics["overflow"] <= 1,
                "mobile_nav": (metrics["mobileNav"] != "none") if width <= 768 else True,
            }
            viewport_results.append({"width": width, "height": height, "metrics": metrics, "checks": checks})
            if not all(checks.values()):
                raise RuntimeError(f"Viewport {width} failed: {checks}, {metrics}")
            await screenshot(f"{width}.png")

        page_cases = [
            (1440, "/heritage-projects", "非遗项目库", "projects-1440.png"),
            (1440, "/heritage-projects/project-miao-embroidery", "可信来源", "project-detail-1440.png"),
            (1440, "/inheritors/person-ajin", "阿锦（演示人物）", "inheritor-1440.png"),
            (1440, "/map?region=region-yunnan", "文化地图", "map-1440.png"),
            (1440, "/topics", "专题策展", "topics-1440.png"),
            (1440, "/events", "非遗活动", "events-1440.png"),
            (768, "/map?region=region-yunnan", "文化地图", "map-768.png"),
            (390, "/heritage-projects", "非遗项目库", "projects-390.png"),
            (390, "/heritage-projects/project-miao-embroidery", "可信来源", "project-detail-390.png"),
            (390, "/inheritors/person-ajin", "阿锦（演示人物）", "inheritor-390.png"),
            (390, "/map?region=region-yunnan", "文化地图", "map-390.png"),
            (390, "/topics", "专题策展", "topics-390.png"),
            (390, "/events", "非遗活动", "events-390.png"),
        ]
        for width, path, expected, name in page_cases:
            height = 844 if width == 390 else 900
            await command(
                "Emulation.setDeviceMetricsOverride",
                {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width <= 768},
            )
            await navigate(path, expected)
            if path.startswith("/map"):
                for _ in range(40):
                    active_region = await evaluate("document.querySelector('.productRegionFilters button[aria-pressed=true]')?.innerText || ''")
                    if str(active_region).startswith("云南"):
                        break
                    await asyncio.sleep(0.1)
            metrics = await evaluate("""(() => ({
              scrollWidth: document.documentElement.scrollWidth,
              viewport: window.innerWidth,
              overflow: Math.max(0, document.documentElement.scrollWidth-window.innerWidth),
              entityCards: document.querySelectorAll('.productEntityCard').length,
              detailSections: document.querySelectorAll('.productDetailSection').length,
              eventCards: document.querySelectorAll('.productEventCard').length,
              activeRegion: document.querySelector('.productRegionFilters button[aria-pressed=true]')?.innerText || null,
              mobileNav: getComputedStyle(document.querySelector('.productMobileNav')).display
            }))()""")
            checks = {
                "expected_copy": expected in str(await evaluate("document.body?.innerText || ''")),
                "no_horizontal_overflow": metrics["overflow"] <= 1,
                "mobile_nav": (metrics["mobileNav"] != "none") if width <= 768 else True,
                "map_deep_link": str(metrics["activeRegion"]).startswith("云南") if path.startswith("/map") else True,
            }
            page_results.append({"width": width, "path": path, "metrics": metrics, "checks": checks, "screenshot": str(ARTIFACTS / name)})
            if not all(checks.values()):
                raise RuntimeError(f"Page {path} at {width}px failed: {checks}, {metrics}")
            await screenshot(name)

        await command(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
        )

        body = await navigate("/content/content-embroidery-01", "关键事实")
        assertions["detail_has_sources"] = all(term in body for term in ["可信摘要", "关键事实", "来源清单"])
        assertions["detail_has_annotations"] = "时间点知识注释" in body
        await wait_for("收藏")
        await click_when_ready("收藏", "button")
        bookmark_state = "false"
        for _ in range(40):
            bookmark_state = await evaluate("document.querySelector('button[aria-label*=" + json.dumps("收藏") + "]')?.getAttribute('aria-pressed')")
            if bookmark_state == "true":
                break
            await asyncio.sleep(0.1)
        assertions["bookmark_button"] = True
        assertions["bookmark_active"] = bookmark_state == "true"
        await command("Page.reload")
        await wait_for("关键事实")
        persisted_state = "false"
        for _ in range(40):
            persisted_state = await evaluate("document.querySelector('button[aria-label*=" + json.dumps("收藏") + "]')?.getAttribute('aria-pressed')")
            if persisted_state == "true":
                break
            await asyncio.sleep(0.1)
        assertions["bookmark_persisted_after_reload"] = persisted_state == "true"

        await navigate("/profile/demo-user?tab=saved", "文化档案")
        body = await wait_for("一根线，怎样绣出远方")
        assertions["saved_visible_in_profile"] = "一根线，怎样绣出远方" in body

        body = await navigate("/search?q=%E8%8B%97%E7%BB%A3", "苗绣")
        assertions["search_content_result"] = "一根线，怎样绣出远方" in body
        assertions["search_project_result"] = "苗绣" in body and "非遗项目" in body

        await navigate("/creator/submissions/new?type=article", "选择内容类型")
        if not await click_text("保存并继续"):
            raise RuntimeError("Could not enter submission asset step")
        await wait_for("登记素材")
        file_added = await evaluate("""(() => {
          const input=document.querySelector('input[type=file]'); if(!input)return false;
          const transfer=new DataTransfer();
          transfer.items.add(new File(['haha demo'], 'demo-cover.png', {type:'image/png'}));
          Object.defineProperty(input,'files',{value:transfer.files,configurable:true});
          input.dispatchEvent(new Event('change',{bubbles:true})); return true;
        })()""")
        assertions["submission_asset_metadata"] = bool(file_added)
        await wait_for("demo-cover.png")
        await click_text("保存并继续")
        await wait_for("填写基础信息")
        form_ready = await evaluate("""(() => {
          const set=(selector,value)=>{const el=document.querySelector(selector);if(!el)return false;
            const proto=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:el.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;
            Object.getOwnPropertyDescriptor(proto,'value').set.call(el,value);
            el.dispatchEvent(new Event(el.tagName==='SELECT'?'change':'input',{bubbles:true}));return true;};
          const selects=[...document.querySelectorAll('select')];
          return {
            title:set('input[maxlength="200"]','一根线里的苗绣故事'),
            summary:set('textarea[maxlength="4000"]','从材料、针法与生活记忆出发的内部演示投稿。'),
            category: selects[0] ? set('select',selects[0].options[1]?.value||'embroidery') : false,
            region: selects[1] ? (()=>{const el=selects[1];Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(el,el.options[1]?.value||'region-guizhou');el.dispatchEvent(new Event('change',{bubbles:true}));return true;})() : false
          };
        })()""")
        assertions["submission_basic_form"] = all(form_ready.values())
        await click_text("保存并继续")
        await wait_for("关联项目、人物与来源")
        linked = await evaluate("""(() => {
          const boxes=[...document.querySelectorAll('input[type=checkbox]')];
          if(boxes.length<2)return false;
          const project=boxes[0]; const source=boxes[boxes.length-1];
          project.click(); source.click(); return project.checked&&source.checked;
        })()""")
        assertions["submission_project_and_source"] = bool(linked)
        await click_text("保存并继续")
        await wait_for("AI 披露与自动检查")
        await click_text("保存并继续")
        body = await wait_for("预览并提交")
        assertions["submission_checks_pass"] = "仍需补充" not in body
        await click_text("提交本地审核")
        body = await wait_for("本地审核状态")
        assertions["submission_submitted"] = "submitted" in body

        await navigate("/review", "审核中心")
        body = await wait_for("一根线里的苗绣故事")
        assertions["review_queue"] = "一根线里的苗绣故事" in body
        await wait_for("开始审核")
        await click_when_ready("开始审核")
        await wait_for("审核中")
        await wait_for("审核通过")
        await click_when_ready("审核通过")
        await wait_for("发布演示内容")
        await click_when_ready("发布演示内容")
        body = await wait_for("已发布（演示）")
        assertions["review_publish_flow"] = "已发布（演示）" in body

        await navigate("/notifications", "消息中心")
        body = await wait_for("投稿状态已更新")
        assertions["review_notifications"] = "投稿状态已更新" in body

        failed_responses = []
        browser_errors = []
        for event in events:
            method = event.get("method")
            params = event.get("params", {})
            if method == "Runtime.exceptionThrown":
                browser_errors.append(event)
            elif method == "Log.entryAdded" and params.get("entry", {}).get("level") in {"error", "warning"}:
                browser_errors.append(event)
            elif method == "Network.responseReceived":
                response = params.get("response", {})
                status = int(response.get("status", 0))
                if status >= 400:
                    failed_responses.append({"status": status, "url": response.get("url")})
            elif method == "Network.loadingFailed" and not params.get("canceled"):
                failed_responses.append({"error": params.get("errorText"), "requestId": params.get("requestId")})

        CONSOLE_REPORT.write_text(
            json.dumps({"browser_errors": browser_errors, "failed_responses": failed_responses}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        assertions["no_browser_exceptions"] = not browser_errors
        assertions["no_failed_http_responses"] = not failed_responses
        if not all(assertions.values()):
            failed = {key: value for key, value in assertions.items() if not value}
            raise RuntimeError(f"Community interaction assertions failed: {failed}")

        await screenshot("final-notifications.png")
        return {
            "status": "passed",
            "base_url": WEB_BASE_URL,
            "viewports": viewport_results,
            "pages": page_results,
            "assertions": assertions,
            "browser_errors": len(browser_errors),
            "failed_responses": len(failed_responses),
            "artifacts": [str(ARTIFACTS / f"{width}.png") for width in VIEWPORTS]
            + [item["screenshot"] for item in page_results]
            + [str(ARTIFACTS / "final-notifications.png"), str(CONSOLE_REPORT)],
        }


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    chrome = find_chrome()
    with tempfile.TemporaryDirectory(
        prefix="haha-community-e2e-", ignore_cleanup_errors=True
    ) as profile:
        process = subprocess.Popen(
            [
                str(chrome),
                "--headless=new",
                f"--remote-debugging-port={DEBUG_PORT}",
                "--remote-allow-origins=*",
                f"--user-data-dir={profile}",
                "--disable-extensions",
                "--disable-translate",
                "--no-first-run",
                "--hide-scrollbars",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            endpoint = f"http://127.0.0.1:{DEBUG_PORT}/json/new?{urllib.parse.quote(WEB_BASE_URL, safe=':/?=&')}"
            target: dict[str, Any] | None = None
            for _ in range(100):
                try:
                    request = urllib.request.Request(endpoint, method="PUT")
                    with urllib.request.urlopen(request, timeout=2) as response:
                        target = json.load(response)
                    break
                except Exception:
                    time.sleep(0.2)
            if not target:
                raise RuntimeError("Chrome DevTools endpoint did not start")
            result = asyncio.run(asyncio.wait_for(run(str(target["webSocketDebuggerUrl"])), 150))
            REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False))
        except Exception as exc:
            REPORT.write_text(
                json.dumps({"status": "failed", "error": repr(exc)}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            raise
        finally:
            process.terminate()
            process.wait(timeout=8)


if __name__ == "__main__":
    main()
