"""Real Chrome acceptance for the API-backed Community Gate C2 UI."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import websockets

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "e2e" / "community-gate-c2-browser"
REPORT = ARTIFACTS / "report.json"
WEB_URL = os.getenv("HAHA_E2E_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
API_URL = os.getenv("HAHA_E2E_API_URL", "http://127.0.0.1:8000").rstrip("/")
DEBUG_PORT = int(os.getenv("HAHA_C2_BROWSER_DEBUG_PORT", "9362"))
USER_ID = os.getenv("HAHA_C2_BROWSER_USER", "local-user")
WORKSPACE = os.getenv("HAHA_C2_BROWSER_WORKSPACE", "local")
LOCAL_ARCHIVE_KEY = "haha.community.state.v1:demo-workspace:demo-user"


def find_chrome() -> Path:
    for candidate in (
        os.getenv("HAHA_E2E_CHROME", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
    ):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    resolved = shutil.which("google-chrome") or shutil.which("chromium")
    if resolved:
        return Path(resolved)
    raise RuntimeError("Chrome or Chromium was not found")


def api(method: str, path: str, payload: dict[str, object] | None = None) -> int:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {
        "X-User-ID": USER_ID,
        "X-Workspace-ID": WORKSPACE,
        "Content-Type": "application/json",
    }
    call = urllib.request.Request(
        f"{API_URL}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(call, timeout=15) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def api_json(path: str) -> dict[str, Any]:
    call = urllib.request.Request(
        f"{API_URL}{path}",
        headers={"X-User-ID": USER_ID, "X-Workspace-ID": WORKSPACE},
        method="GET",
    )
    with urllib.request.urlopen(call, timeout=15) as response:
        return json.loads(response.read())


def prepare_identity() -> None:
    if api("GET", "/api/community/bootstrap") != 200:
        raise RuntimeError("Community bootstrap failed before browser test")
    if api("POST", "/api/identity/roles/creator/activate") != 200:
        raise RuntimeError("Could not activate creator role")
    if api("POST", "/api/identity/context", {"role": "creator"}) != 200:
        raise RuntimeError("Could not switch creator context")
    api("DELETE", "/api/community/contents/content-embroidery-01/reactions/bookmark")


async def run(websocket_url: str) -> dict[str, Any]:
    next_id = 0
    events: list[dict[str, Any]] = []
    assertions: dict[str, bool] = {}
    viewports: list[dict[str, Any]] = []
    screenshots: list[str] = []

    async with websockets.connect(websocket_url, max_size=30_000_000) as socket:
        async def command(
            method: str, params: dict[str, Any] | None = None
        ) -> dict[str, Any]:
            nonlocal next_id
            next_id += 1
            current = next_id
            await socket.send(json.dumps({
                "id": current, "method": method, "params": params or {},
            }))
            while True:
                message = json.loads(await asyncio.wait_for(socket.recv(), timeout=25))
                if message.get("id") == current:
                    if "error" in message:
                        raise RuntimeError(message["error"])
                    return message.get("result", {})
                events.append(message)

        async def evaluate(expression: str) -> Any:
            result = await command("Runtime.evaluate", {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            })
            if result.get("exceptionDetails"):
                raise RuntimeError(result["exceptionDetails"])
            return result.get("result", {}).get("value")

        async def wait_for(fragment: str, timeout: float = 25) -> str:
            deadline = time.monotonic() + timeout
            body = ""
            while time.monotonic() < deadline:
                body = str(await evaluate("document.body?.innerText || ''"))
                if fragment in body:
                    return body
                await asyncio.sleep(0.25)
            raise TimeoutError(
                f"Timed out waiting for {fragment!r}; body tail: {body[-1200:]}"
            )

        async def navigate(path: str, expected: str) -> str:
            await command("Page.navigate", {"url": f"{WEB_URL}{path}"})
            return await wait_for(expected)

        async def click(fragment: str) -> bool:
            return bool(await evaluate(f"""(() => {{
              const text={json.dumps(fragment)};
              const node=[...document.querySelectorAll('button,a')]
                .find((item)=>(item.innerText||item.textContent||'').includes(text)&&!item.disabled);
              if(!node) return false; node.click(); return true;
            }})()"""))

        async def click_ready(fragment: str, timeout: float = 25) -> None:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if await click(fragment):
                    return
                await asyncio.sleep(0.25)
            raise TimeoutError(f"Could not click {fragment!r}")

        async def screenshot(name: str) -> None:
            shot = await command("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": True,
            })
            target = ARTIFACTS / name
            target.write_bytes(base64.b64decode(shot["data"]))
            screenshots.append(str(target))

        await command("Runtime.enable")
        await command("Page.enable")
        await command("Log.enable")
        await command("Network.enable")

        for width in (390, 768, 1024, 1440):
            await command("Emulation.setDeviceMetricsOverride", {
                "width": width,
                "height": 900,
                "deviceScaleFactor": 1,
                "mobile": width <= 768,
            })
            body = await navigate("/community", "内容 Feed")
            for _ in range(80):
                card_count = int(await evaluate(
                    "document.querySelectorAll('.contentCard').length"
                ))
                if card_count >= 10:
                    break
                current_body = str(await evaluate("document.body?.innerText || ''"))
                if "服务端内容暂时不可用" in current_body:
                    break
                await asyncio.sleep(0.15)
            metrics = await evaluate("""(() => ({
              viewport: innerWidth,
              scrollWidth: document.documentElement.scrollWidth,
              cards: document.querySelectorAll('.contentCard').length,
              badge: document.querySelector('.brandBanner span')?.innerText || ''
            }))()""")
            checks = {
                "api_copy": "服务端内部测试数据" in body,
                "cards": metrics["cards"] >= 10,
                "no_overflow": metrics["scrollWidth"] <= metrics["viewport"] + 1,
            }
            if not all(checks.values()):
                raise RuntimeError(f"Viewport {width} failed: {checks} {metrics}")
            viewports.append({"width": width, "checks": checks, "metrics": metrics})
            await screenshot(f"community-{width}.png")

        await command("Emulation.setDeviceMetricsOverride", {
            "width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False,
        })
        body = await navigate(
            "/content/content-embroidery-01", "服务端内容闭环"
        )
        assertions["detail_from_api"] = all(
            value in body for value in ("关键事实", "来源清单", "账户互动")
        )
        await click_ready("收藏")
        for _ in range(40):
            active = await evaluate(
                "document.querySelector('button[aria-label*=收藏]')?.getAttribute('aria-pressed')"
            )
            if active == "true":
                break
            await asyncio.sleep(0.1)
        assertions["bookmark_written"] = active == "true"
        await command("Page.reload")
        await wait_for("服务端内容闭环")
        for _ in range(40):
            active = await evaluate(
                "document.querySelector('button[aria-label*=收藏]')?.getAttribute('aria-pressed')"
            )
            if active == "true":
                break
            await asyncio.sleep(0.1)
        assertions["bookmark_survives_reload"] = active == "true"
        await screenshot("content-api-state.png")

        published_snapshot = api_json("/api/community/bootstrap")
        published_candidates = [
            item for item in published_snapshot.get("contents", [])
            if item.get("provenance") == "creator_submission"
            and any(asset.get("kind") == "video" and asset.get("url") for asset in item.get("media", []))
        ]
        published_media_content = max(
            published_candidates, key=lambda item: str(item.get("updatedAt", "")), default=None
        )
        assertions["published_video_discoverable"] = published_media_content is not None
        if published_media_content:
            await navigate(
                f"/content/{urllib.parse.quote(str(published_media_content['id']))}",
                "已审核发布素材",
            )
            playback_started = await evaluate("""(async () => {
              const video=document.querySelector('video'); if(!video)return false;
              video.muted=true; await video.play();
              await new Promise((resolve)=>setTimeout(resolve,350));
              return video.currentTime>0 || video.ended;
            })()""")
            assertions["published_video_browser_playback"] = bool(playback_started)
            await screenshot("published-video-playback.png")
        else:
            assertions["published_video_browser_playback"] = False

        archive_marker = f"browser-migration-{int(time.time() * 1000)}"
        local_archive = {
            "schemaVersion": 1,
            "revision": 1,
            "viewerId": "demo-user",
            "workspaceId": "demo-workspace",
            "reactions": {"content-dyeing-01": ["want_to_learn"]},
            "followingPersonIds": ["person-nanqing"],
            "history": [{
                "contentId": "content-dyeing-01",
                "viewedAt": "2026-10-15T00:00:00.000Z",
                "progressSeconds": 12,
                "completed": False,
            }],
            "comments": [{
                "id": f"comment-{archive_marker}",
                "contentId": "content-dyeing-01",
                "body": "浏览器迁移评论",
            }],
            "annotations": [{
                "id": f"annotation-{archive_marker}",
                "contentId": "content-dyeing-01",
                "timestampSeconds": 2,
                "body": "浏览器迁移注释",
                "kind": "source",
                "sourceIds": ["source-bai-dyeing"],
                "verificationStatus": "verified",
            }],
            "drafts": [{
                "id": f"draft-{archive_marker}",
                "submissionType": "article",
                "status": "published",
                "title": f"迁移状态降级验证 {archive_marker}",
                "summary": "本地发布状态必须降级为服务端草稿。",
                "projectIds": ["project-bai-dyeing"],
                "personIds": [],
                "sourceIds": ["source-bai-dyeing"],
                "tags": ["迁移测试"],
                "assets": [],
                "aiDisclosure": "none",
            }],
            "notifications": [{"id": "must-not-import"}],
            "searchHistory": ["must-not-import"],
        }
        await evaluate(
            f"window.localStorage.setItem({json.dumps(LOCAL_ARCHIVE_KEY)}, "
            f"{json.dumps(json.dumps(local_archive, ensure_ascii=False))}); true"
        )

        body = await navigate(f"/profile/{USER_ID}?tab=saved", "文化账户档案")
        assertions["account_archive"] = "一根线，怎样绣出远方" in body
        await wait_for("迁移浏览器文化档案")
        await click_ready("检查本地档案")
        body = await wait_for("不会迁移")
        assertions["archive_migration_preview"] = all(
            value in body for value in ("互动目标", "关注人物", "贡献与草稿")
        )
        await click_ready("确认迁移到当前账户")
        body = await wait_for("迁移完成")
        assertions["archive_migration_completed"] = all(
            value in body for value in ("注释 1", "草稿 1", "本地核验、审核和发布状态均未导入")
        )
        assertions["archive_source_preserved"] = bool(await evaluate(
            f"window.localStorage.getItem({json.dumps(LOCAL_ARCHIVE_KEY)})"
        ))
        await click_ready("投稿管理")
        body = await wait_for(archive_marker)
        assertions["archive_trust_downgraded"] = "草稿" in body and "已发布（演示）" not in body
        await screenshot("archive-migration-server-state.png")

        body = await navigate("/review", "当前身份不能进入审核工作台")
        assertions["reviewer_role_boundary_ui"] = "创作者不能审核自己的投稿" in body

        await navigate("/creator/submissions/new?type=article", "选择内容类型")
        await click_ready("保存并继续")
        await wait_for("上传素材")
        assertions["asset_binary_uploaded"] = bool(await evaluate("""(() => {
          const input=document.querySelector('input[type=file]'); if(!input)return false;
          const transfer=new DataTransfer();
          transfer.items.add(new File([new Uint8Array([137,80,78,71,13,10,26,10,0,0,0,0])], 'c2-browser.png', {type:'image/png'}));
          Object.defineProperty(input,'files',{value:transfer.files,configurable:true});
          input.dispatchEvent(new Event('change',{bubbles:true})); return true;
        })()"""))
        await wait_for("服务端已上传并校验")
        await click_ready("保存并继续")
        await wait_for("填写基础信息")
        fields = await evaluate("""(() => {
          const set=(selector,value)=>{const el=document.querySelector(selector);if(!el)return false;
            const proto=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:el.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;
            Object.getOwnPropertyDescriptor(proto,'value').set.call(el,value);
            el.dispatchEvent(new Event(el.tagName==='SELECT'?'change':'input',{bubbles:true}));return true;};
          const selects=[...document.querySelectorAll('select')];
          return {
            title:set('input[maxlength="200"]','C2 浏览器真实投稿'),
            summary:set('textarea[maxlength="4000"]','通过真实浏览器验证服务端草稿、版本和提交状态。'),
            category:selects[0]?set('select',selects[0].options[1]?.value||'刺绣'):false,
            region:selects[1]?(()=>{const el=selects[1];Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(el,el.options[1]?.value);el.dispatchEvent(new Event('change',{bubbles:true}));return true;})():false
          };
        })()""")
        assertions["submission_fields"] = all(fields.values())
        await click_ready("保存并继续")
        await wait_for("关联项目、人物与来源")
        assertions["submission_links"] = bool(await evaluate("""(() => {
          const boxes=[...document.querySelectorAll('input[type=checkbox]')];
          if(boxes.length<2)return false; boxes[0].click(); boxes[boxes.length-1].click();
          return boxes[0].checked&&boxes[boxes.length-1].checked;
        })()"""))
        await click_ready("保存并继续")
        await wait_for("AI 披露与自动检查")
        await click_ready("保存并继续")
        body = await wait_for("预览并提交")
        assertions["submission_checks"] = "仍需补充" not in body
        await click_ready("提交内部审核")
        await wait_for("服务端审核状态")
        body = ""
        for _ in range(80):
            body = str(await evaluate("document.body?.innerText || ''"))
            if "submitted" in body:
                break
            await asyncio.sleep(0.15)
        assertions["submission_persisted"] = "submitted" in body
        await screenshot("submission-server-state.png")

        await command("Network.setBlockedURLs", {
            "urls": [f"{API_URL}/api/community/*"],
        })
        body = await navigate("/community?api-failure=1", "服务端内容暂时不可用")
        assertions["api_failure_no_local_fallback"] = (
            "服务端数据不可用" in body
            and await evaluate("document.querySelectorAll('.contentCard').length") == 0
        )
        await screenshot("api-failure-no-fallback.png")
        await command("Network.setBlockedURLs", {"urls": []})

        browser_errors = []
        for event in events:
            method = event.get("method")
            entry = event.get("params", {}).get("entry", {})
            if method == "Runtime.exceptionThrown":
                browser_errors.append(event)
            elif method == "Log.entryAdded" and entry.get("level") == "error":
                text = str(entry.get("text", ""))
                if "ERR_FAILED" not in text and "Failed to fetch" not in text:
                    browser_errors.append(event)
        assertions["no_unexpected_browser_errors"] = not browser_errors
        status = "PASS" if all(assertions.values()) else "FAIL"
        return {
            "status": status,
            "web_url": WEB_URL,
            "viewports": viewports,
            "assertions": assertions,
            "browser_errors": browser_errors,
            "screenshots": screenshots,
        }


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    prepare_identity()
    chrome = find_chrome()
    with tempfile.TemporaryDirectory(
        prefix="haha-c2-browser-", ignore_cleanup_errors=True
    ) as profile:
        process = subprocess.Popen(
            [
                str(chrome),
                "--headless=new",
                f"--remote-debugging-port={DEBUG_PORT}",
                "--remote-allow-origins=*",
                f"--user-data-dir={profile}",
                "--disable-extensions",
                "--no-first-run",
                "--hide-scrollbars",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            endpoint = (
                f"http://127.0.0.1:{DEBUG_PORT}/json/new?"
                f"{urllib.parse.quote(WEB_URL, safe=':/?=&')}"
            )
            target: dict[str, Any] | None = None
            for _ in range(100):
                try:
                    call = urllib.request.Request(endpoint, method="PUT")
                    with urllib.request.urlopen(call, timeout=2) as response:
                        target = json.load(response)
                    break
                except Exception:
                    time.sleep(0.2)
            if not target:
                raise RuntimeError("Chrome DevTools endpoint did not start")
            result = asyncio.run(asyncio.wait_for(
                run(str(target["webSocketDebuggerUrl"])), 180
            ))
            REPORT.write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps(result, ensure_ascii=False))
            if result["status"] != "PASS":
                raise SystemExit(1)
        except Exception as exc:
            REPORT.write_text(
                json.dumps({"status": "FAIL", "error": repr(exc)}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            raise
        finally:
            process.terminate()
            process.wait(timeout=8)


if __name__ == "__main__":
    main()
