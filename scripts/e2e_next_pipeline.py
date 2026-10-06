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
APP_URL = os.getenv("HAHA_E2E_WEB_URL", "http://127.0.0.1:3000")


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

        await command("Runtime.enable")
        await command("Page.enable")
        await command("Log.enable")
        await command(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1680, "height": 1050, "deviceScaleFactor": 1, "mobile": False},
        )
        await command("Page.navigate", {"url": APP_URL})
        await wait_for("生成本次创作判断")
        token_saved = await evaluate(
            f"(() => {{sessionStorage.setItem('haha_access_token',{json.dumps(token)});return Boolean(sessionStorage.getItem('haha_access_token'));}})()"
        )
        if not token_saved:
            raise RuntimeError("Could not store the short-lived staging token")
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
                tone:setSelect('表达气质','纪录片')
              };
            })()"""
        )
        if not all(prepared.values()):
            raise RuntimeError(f"Could not prepare form: {prepared}")
        await asyncio.sleep(0.75)
        clicked = await evaluate(
            "(() => {const button=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('生成本次创作判断'));button?.click();return !!button;})()"
        )
        if not clicked:
            raise RuntimeError("Submit button not found")
        body = await wait_for("验收通过", 60)
        checks = {
            "platform": "推荐平台 · B站" in body,
            "spec": "推荐规格 · 90秒 · 16:9" in body,
            "tone": "表达气质 · 纪录片" in body,
            "verification": "独立验收已通过" in body,
            "evidence": "事实来源" in body,
        }
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
            "checks": checks,
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
