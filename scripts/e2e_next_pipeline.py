"""Real-browser Next.js -> FastAPI -> Worker -> PostgreSQL pipeline check."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import websockets

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "e2e"
ARTIFACT_PREFIX = os.getenv("HAHA_E2E_ARTIFACT_PREFIX", "phase-b-next-pipeline")
SCREENSHOT = ARTIFACTS / f"{ARTIFACT_PREFIX}.png"
REPORT = ARTIFACTS / f"{ARTIFACT_PREFIX}.json"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
DEBUG_PORT = 9340
VIEWPORT_WIDTH = int(os.getenv("HAHA_E2E_VIEWPORT_WIDTH", "1680"))
WEB_BASE_URL = os.getenv("HAHA_E2E_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
APP_URL = WEB_BASE_URL if WEB_BASE_URL.endswith("/creator") else f"{WEB_BASE_URL}/creator"
CANCEL_MODE = os.getenv("HAHA_E2E_CANCEL_MODE", "false").lower() == "true"
OPERATIONS_MODE = os.getenv("HAHA_E2E_OPERATIONS_MODE", "false").lower() == "true"


async def run(websocket_url: str, token: str) -> dict[str, Any]:
    next_id = 0
    events: list[dict[str, Any]] = []
    async with websockets.connect(websocket_url, max_size=20_000_000) as socket:
        async def command(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            nonlocal next_id
            next_id += 1
            command_id = next_id
            await socket.send(json.dumps({"id": command_id, "method": method, "params": params or {}}))
            while True:
                message = json.loads(await asyncio.wait_for(socket.recv(), timeout=20))
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
            return result.get("result", {}).get("value")

        async def wait_for(fragment: str, timeout: float = 45) -> str:
            deadline = time.monotonic() + timeout
            body = ""
            while time.monotonic() < deadline:
                body = str(await evaluate("document.body?.innerText || ''"))
                if fragment in body:
                    return body
                await asyncio.sleep(0.5)
            raise TimeoutError(f"Timed out waiting for {fragment!r}; body tail: {body[-1600:]}")

        async def wait_until_missing(fragment: str, timeout: float = 20) -> str:
            deadline = time.monotonic() + timeout
            body = ""
            while time.monotonic() < deadline:
                body = str(await evaluate("document.body?.innerText || ''"))
                if fragment not in body:
                    return body
                await asyncio.sleep(0.5)
            raise TimeoutError(f"Timed out waiting for {fragment!r} to disappear")

        async def wait_for_action(text: str, selector: str, timeout: float = 20) -> bool:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                found = await evaluate(
                    f"[...document.querySelectorAll({json.dumps(selector)})].some(x=>x.textContent.includes({json.dumps(text)}))"
                )
                if found:
                    return True
                await asyncio.sleep(0.5)
            raise TimeoutError(f"Timed out waiting for action {text!r}")

        async def wait_for_handoff_ready(timeout: float = 20) -> bool:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                ready = await evaluate(
                    "document.querySelector('.resultActions a')?.getAttribute('aria-disabled') === 'false'"
                )
                if ready:
                    return True
                await asyncio.sleep(0.5)
            raise TimeoutError("Timed out waiting for reviewed handoff state")

        await command("Runtime.enable")
        await command("Page.enable")
        await command("Log.enable")
        await command("Network.enable")
        await command(
            "Emulation.setDeviceMetricsOverride",
            {"width": VIEWPORT_WIDTH, "height": 1050, "deviceScaleFactor": 1, "mobile": VIEWPORT_WIDTH < 600},
        )
        await command("Page.navigate", {"url": APP_URL})
        await wait_for("生成引擎")
        token_saved = await evaluate(
            f"(() => {{sessionStorage.setItem('haha_access_token',{json.dumps(token)});return Boolean(sessionStorage.getItem('haha_access_token'));}})()"
        )
        if not token_saved:
            raise RuntimeError("Could not store the short-lived staging token")
        await wait_for("DeepSeek V4.1 Flash", 20)
        if OPERATIONS_MODE:
            refreshed = await evaluate(
                "(() => {const button=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('刷新列表'));button?.click();return !!button;})()"
            )
            if not refreshed:
                raise RuntimeError("Failed-job refresh button not found")
            body = await wait_for("C4_E2E_FAILURE", 20)
            resolved = await evaluate(
                "(() => {const button=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('标记已处理'));button?.click();return !!button;})()"
            )
            if not resolved:
                raise RuntimeError("Failed-job resolve button not found")
            body = await wait_until_missing("C4_E2E_FAILURE", 20)
            requests = [
                event.get("params", {}).get("request", {})
                for event in events
                if event.get("method") == "Network.requestWillBeSent"
            ]
            checks = {
                "operations_ui": "失败任务运维" in body,
                "failed_job_list": any(
                    str(request.get("url", "")).endswith("/api/failed-jobs")
                    and request.get("method") == "GET"
                    for request in requests
                ),
                "failed_job_resolve": any(
                    str(request.get("url", "")).endswith("/resolve")
                    and request.get("method") == "POST"
                    for request in requests
                ),
                "resolved_removed": "C4_E2E_FAILURE" not in body,
            }
            if not all(checks.values()):
                raise RuntimeError(f"Failed-job operations UI check failed: {checks}")
            shot = await command(
                "Page.captureScreenshot",
                {"format": "png", "captureBeyondViewport": True, "fromSurface": True},
            )
            SCREENSHOT.write_bytes(base64.b64decode(shot["data"]))
            exceptions = [
                event for event in events
                if event.get("method") in {"Runtime.exceptionThrown", "Log.entryAdded"}
            ]
            return {
                "status": "passed",
                "url": APP_URL,
                "mode": "operations",
                "checks": checks,
                "browser_exceptions": exceptions,
                "screenshot": str(SCREENSHOT),
            }
        prepared = await evaluate(
            """(() => {
              const setInput=(labelText,value)=>{
                const label=[...document.querySelectorAll('label')].find(x=>x.innerText.includes(labelText));
                const el=label?.querySelector('input,textarea'); if(!el)return false;
                const setter=Object.getOwnPropertyDescriptor(el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set;
                setter.call(el,value); el.dispatchEvent(new Event('input',{bubbles:true})); return true;
              };
              const setSelect=(labelText,value)=>{
                const label=[...document.querySelectorAll('label')].find(x=>x.innerText.includes(labelText));
                const el=label?.querySelector('select'); if(!el)return false;
                const setter=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set;
                setter.call(el,value); el.dispatchEvent(new Event('change',{bubbles:true})); return true;
              };
              return {
                craft:setInput('创作主题','中国剪纸'),
                story:setInput('想讲的一个瞬间','剪刀落下形成纹样'),
                platform:setSelect('发布平台','B站'),
                duration:setSelect('成片时长','90秒'),
                ratio:setSelect('画幅','16:9'),
                tone:setSelect('表达气质','纪录片'),
                engine:setSelect('生成引擎','本地演示')
              };
            })()"""
        )
        if not all(prepared.values()):
            raise RuntimeError(f"Could not prepare form: {prepared}")
        await asyncio.sleep(0.75)
        clicked = await evaluate(
            "(() => {const button=document.querySelector('.generateButton');button?.click();return !!button;})()"
        )
        if not clicked:
            raise RuntimeError("Submit button not found")
        if CANCEL_MODE:
            await wait_for("取消本次运行", 20)
            cancelled = await evaluate(
                "(() => {const button=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('取消本次运行'));button?.click();return !!button;})()"
            )
            if not cancelled:
                raise RuntimeError("Cancel button not found")
            body = await wait_for("运行已取消", 20)
        else:
            body = await wait_for("验收通过", 60)
            creator_body = body
            revision_opened = await evaluate(
                "(() => {const button=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='人工修订');button?.click();return !!button;})()"
            )
            if not revision_opened:
                raise RuntimeError("Human revision button not found")
            await wait_for("原始生成版本不会被覆盖", 10)
            revision_prepared = await evaluate(
                """(() => {
                  const editor=document.querySelector('.revisionEditor');
                  const input=editor?.querySelector('input');
                  if(!input)return false;
                  const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                  setter.call(input,input.value+'（浏览器修订）');
                  input.dispatchEvent(new Event('input',{bubbles:true}));
                  return true;
                })()"""
            )
            if not revision_prepared:
                raise RuntimeError("Could not edit revision title")
            saved = await evaluate(
                "(() => {const button=[...document.querySelectorAll('.revisionEditor button')].find(x=>x.textContent.includes('保存新版本'));button?.click();return !!button;})()"
            )
            if not saved:
                raise RuntimeError("Save revision button not found")
            await wait_for_action("确认人工复核", ".resultActions button", 20)
            reviewed = await evaluate(
                "(() => {const button=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('确认人工复核'));button?.click();return !!button;})()"
            )
            if not reviewed:
                raise RuntimeError("Review revision button not found")
            await wait_for_handoff_ready(20)
            body = str(await evaluate("document.body?.innerText || ''"))
            handoff_clicked = await evaluate(
                "(() => {const link=[...document.querySelectorAll('a')].find(x=>x.textContent.includes('进入投稿预览'));link?.click();return !!link;})()"
            )
            if not handoff_clicked:
                raise RuntimeError("Submission handoff link not found")
            submission_body = await wait_for("已从服务端已复核版本带入", 20)
        requests = [
            event.get("params", {}).get("request", {})
            for event in events
            if event.get("method") == "Network.requestWillBeSent"
        ]
        run_status_requests = [
            request for request in requests
            if request.get("method") == "GET"
            and "/api/runs/" in str(request.get("url", ""))
            and "/events" not in str(request.get("url", ""))
            and "/submission-handoff" not in str(request.get("url", ""))
            and "/script-revisions" not in str(request.get("url", ""))
        ]
        checks = {
            "sse_progress": any(
                "/api/runs/" in str(request.get("url", ""))
                and "/events" in str(request.get("url", ""))
                for request in requests
            ),
            "polling_replaced": len(run_status_requests) <= 1,
            "operations_ui": "失败任务运维" in body,
        }
        if CANCEL_MODE:
            checks.update({
                "cancelled_ui": "运行已取消" in body,
                "cancel_request": any(
                    str(request.get("url", "")).endswith("/cancel")
                    and request.get("method") == "POST"
                    for request in requests
                ),
            })
        else:
            checks.update({
                "platform": "推荐平台 · B站" in creator_body,
                "spec": "推荐规格 · 90秒 · 16:9" in creator_body,
                "tone": "表达气质 · 纪录片" in creator_body,
                "verification": "独立验收已通过" in creator_body,
                "evidence": "事实来源" in creator_body,
                "revision_reviewed": True,
                "server_handoff": "已从服务端已复核版本带入" in submission_body,
            })
        if not all(checks.values()):
            raise RuntimeError(f"Generated result did not follow parameters: {checks}")
        shot = await command(
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": True, "fromSurface": True},
        )
        SCREENSHOT.write_bytes(base64.b64decode(shot["data"]))
        exceptions = [
            event for event in events
            if event.get("method") in {"Runtime.exceptionThrown", "Log.entryAdded"}
        ]
        return {
            "status": "passed",
            "url": APP_URL,
            "mode": "cancel" if CANCEL_MODE else "generate",
            "checks": checks,
            "run_status_request_count": len(run_status_requests),
            "browser_exceptions": exceptions,
            "screenshot": str(SCREENSHOT),
        }


def main() -> None:
    token = os.environ["HAHA_E2E_ACCESS_TOKEN"]
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    profile = ARTIFACTS / f"chrome-profile-{time.time_ns()}"
    process = subprocess.Popen(
        [
            str(CHROME),
            "--headless=new",
            f"--remote-debugging-port={DEBUG_PORT}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            "--disable-extensions",
            "--disable-translate",
            "--no-first-run",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        endpoint = f"http://127.0.0.1:{DEBUG_PORT}/json/new?{urllib.parse.quote(APP_URL, safe=':/?=&')}"
        target: dict[str, Any] | None = None
        for _ in range(80):
            try:
                request = urllib.request.Request(endpoint, method="PUT")
                with urllib.request.urlopen(request, timeout=2) as response:
                    target = json.load(response)
                break
            except Exception:
                time.sleep(0.25)
        if not target:
            raise RuntimeError("Chrome DevTools endpoint did not start")
        result = asyncio.run(asyncio.wait_for(run(str(target["webSocketDebuggerUrl"]), token), 90))
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
        process.wait(timeout=5)


if __name__ == "__main__":
    main()
