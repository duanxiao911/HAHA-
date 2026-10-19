"""Real Chrome acceptance for the Gate C3 learning center."""

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
from uuid import uuid4

import websockets

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "e2e" / "learning-gate-c3-browser"
WEB_URL = os.getenv("HAHA_E2E_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
API_URL = os.getenv("HAHA_E2E_API_URL", "http://127.0.0.1:8000").rstrip("/")
DEBUG_PORT = int(os.getenv("HAHA_C3_E2E_DEBUG_PORT", "9363"))
SUFFIX = uuid4().hex[:10]
HEADERS = {"X-User-ID": f"c3-browser-{SUFFIX}", "X-Workspace-ID": f"c3-browser-{SUFFIX}"}


def find_chrome() -> Path:
    for candidate in (
        os.getenv("HAHA_E2E_CHROME", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome", "/usr/bin/chromium",
    ):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    resolved = shutil.which("google-chrome") or shutil.which("chromium")
    if resolved:
        return Path(resolved)
    raise RuntimeError("Chrome or Chromium was not found")


def activate_learner() -> None:
    call = urllib.request.Request(
        f"{API_URL}/api/identity/roles/learner/activate",
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(call, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"Learner activation failed: {response.status}")


async def run(websocket_url: str) -> dict[str, Any]:
    command_id = 0
    events: list[dict[str, Any]] = []
    screenshots: list[str] = []
    assertions: dict[str, bool] = {}
    viewports: list[dict[str, Any]] = []
    async with websockets.connect(websocket_url, max_size=30_000_000) as socket:
        async def command(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            nonlocal command_id
            command_id += 1
            current = command_id
            await socket.send(json.dumps({"id": current, "method": method, "params": params or {}}))
            while True:
                message = json.loads(await asyncio.wait_for(socket.recv(), timeout=30))
                if message.get("id") == current:
                    if "error" in message:
                        raise RuntimeError(message["error"])
                    return message.get("result", {})
                events.append(message)

        async def evaluate(expression: str) -> Any:
            result = await command("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
            if result.get("exceptionDetails"):
                raise RuntimeError(result["exceptionDetails"])
            return result.get("result", {}).get("value")

        async def wait_for(text: str, timeout: float = 30) -> str:
            deadline = time.monotonic() + timeout
            body = ""
            while time.monotonic() < deadline:
                body = str(await evaluate("document.body?.innerText || ''"))
                if text in body:
                    return body
                await asyncio.sleep(0.25)
            raise TimeoutError(f"Timed out waiting for {text!r}: {body[-1200:]}")

        async def click(text: str) -> None:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                clicked = await evaluate(f"""(() => {{const target={json.dumps(text)}; const node=[...document.querySelectorAll('button,a')].find(item=>!item.disabled && (item.innerText||'').trim()===target); if(!node)return false; node.click(); return true;}})()""")
                if clicked:
                    return
                await asyncio.sleep(0.25)
            raise TimeoutError(f"Could not click {text!r}")

        async def shot(name: str) -> None:
            result = await command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
            path = ARTIFACTS / name
            path.write_bytes(base64.b64decode(result["data"]))
            screenshots.append(str(path))

        await command("Runtime.enable")
        await command("Page.enable")
        await command("Network.enable")
        await command("Network.setExtraHTTPHeaders", {"headers": HEADERS})
        for width in (390, 768, 1440):
            await command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width <= 768})
            await command("Page.navigate", {"url": f"{WEB_URL}/learning"})
            body = await wait_for("学习成长中心")
            metrics = await evaluate("({viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth,mobileNav:document.querySelectorAll('.productMobileNav a').length})")
            checks = {
                "loaded": "AI 非遗老师" in body and "DeepSeek" in body,
                "honest_catalog": "非权威认定" in body,
                "no_overflow": metrics["scrollWidth"] <= metrics["viewport"] + 1,
                "responsive_navigation": width > 768 or metrics["mobileNav"] == 5,
            }
            if not all(checks.values()):
                raise RuntimeError({"viewport": width, "checks": checks, "metrics": metrics})
            await shot(f"learning-{width}.png")
            viewports.append({"width": width, "checks": checks, "metrics": metrics})

        await command("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        await command("Page.navigate", {"url": f"{WEB_URL}/learning"})
        await wait_for("加入学习路径")
        await click("加入学习路径")
        await wait_for("学习路径已加入")
        await click("完成节点")
        await wait_for("确认完成这个学习节点")
        await shot("learning-complete-confirm.png")
        await click("确认完成节点")
        await wait_for("学习节点已完成")
        changed = await evaluate("""(() => {const topic=document.querySelector('[data-testid="knowledge-card-form"] input'); const body=document.querySelector('[data-testid="knowledge-card-form"] textarea'); if(!topic||!body)return false; const set=(node,value)=>{const proto=node.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto,'value').set.call(node,value); node.dispatchEvent(new Event('input',{bubbles:true}));}; set(topic,'浏览器来源检查'); set(body,'记录来源、版本和可信状态，不把演示目录当作权威事实。'); return true;})()""")
        assertions["card_form_filled"] = bool(changed)
        await click("保存知识卡")
        await wait_for("知识卡已保存")
        selected = await evaluate("""(() => {const fields=[...document.querySelectorAll('[data-testid="quiz-form"] fieldset')]; fields.forEach(field=>field.querySelectorAll('input[type=radio]')[1]?.click()); return fields.length;})()""")
        assertions["quiz_answers_selected"] = selected == 3
        await click("提交答案")
        body = await wait_for("最近结果：100 分")
        assertions["server_quiz_pass_visible"] = "通过" in body
        await command("Page.reload")
        body = await wait_for("路径完成")
        assertions["refresh_restored_progress"] = "2\n已完成节点" in body or "2\r\n已完成节点" in body
        assertions["daily_tasks_completed"] = body.count("✓") >= 3
        assertions["achievements_visible"] = all(
            label in body for label in ("第一步", "有据可查", "检验理解")
        )
        tutor_available = bool(
            await evaluate("Boolean(document.querySelector('[data-testid=ai-tutor]'))")
        )
        if tutor_available:
            tutor_filled = await evaluate("""(() => {const field=document.querySelector('#tutor-question'); if(!field)return false; const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set; setter.call(field,'中国剪纸有哪些主要特点？'); field.dispatchEvent(new Event('input',{bubbles:true})); return true;})()""")
            assertions["tutor_question_filled"] = bool(tutor_filled)
            await click("提问")
            body = await wait_for("真实模型回答")
            assertions["real_tutor_answer_visible"] = (
                "[F-096] 中国剪纸" in body and "打开来源入口" in body
            )
            await command("Page.reload")
            body = await wait_for("真实模型回答")
            assertions["tutor_history_restored"] = "[F-096] 中国剪纸" in body
        else:
            body = str(await evaluate("document.body?.innerText || ''"))
            assertions["tutor_blocked_without_credentials"] = all(
                text in body
                for text in ("BLOCKED", "AI 非遗老师尚未接通", "真实 DeepSeek 模型凭据")
            )
            assertions["blocked_tutor_has_no_fake_controls_or_answer"] = not bool(
                await evaluate(
                    "Boolean(document.querySelector('#tutor-question, [data-testid=ai-tutor]'))"
                )
            )
            await command("Page.reload")
            body = await wait_for("AI 非遗老师尚未接通")
            assertions["blocked_tutor_boundary_restored"] = "BLOCKED" in body
        await click("查看用户中心成长汇总")
        body = await wait_for("文化足迹与成长状态")
        assertions["growth_deep_link"] = "tab=archive" in str(await evaluate("location.search"))
        assertions["user_center_synced"] = "已完成学习节点" in body and "学习成就" in body
        await shot("learning-final.png")
        browser_errors = [item for item in events if item.get("method") in {"Runtime.exceptionThrown", "Log.entryAdded"}]
        assertions["no_browser_exceptions"] = not browser_errors
        if not all(assertions.values()):
            raise RuntimeError({key: value for key, value in assertions.items() if not value})
        return {"status": "passed", "user": HEADERS["X-User-ID"], "viewports": viewports, "assertions": assertions, "browser_errors": len(browser_errors), "screenshots": screenshots}


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    activate_learner()
    with tempfile.TemporaryDirectory(prefix="haha-c3-e2e-", ignore_cleanup_errors=True) as profile:
        process = subprocess.Popen([str(find_chrome()), "--headless=new", f"--remote-debugging-port={DEBUG_PORT}", "--remote-allow-origins=*", f"--user-data-dir={profile}", "--disable-extensions", "--no-first-run", "--hide-scrollbars", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            endpoint = f"http://127.0.0.1:{DEBUG_PORT}/json/new?{urllib.parse.quote(WEB_URL, safe=':/?=&')}"
            target = None
            for _ in range(100):
                try:
                    with urllib.request.urlopen(urllib.request.Request(endpoint, method="PUT"), timeout=2) as response:
                        target = json.load(response)
                    break
                except OSError:
                    time.sleep(0.15)
            if not target:
                raise RuntimeError("Chrome debug endpoint did not start")
            report = asyncio.run(run(target["webSocketDebuggerUrl"]))
            (ARTIFACTS / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
