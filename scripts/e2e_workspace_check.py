"""Run a real browser smoke test against the local HAHA Streamlit workspace."""

from __future__ import annotations

import asyncio
import base64
import json
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import websockets

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
PROFILE = ARTIFACTS / "e2e-chrome-profile"
SCREENSHOT = ARTIFACTS / "workspace-e2e-result.png"
REPORT = ARTIFACTS / "workspace-e2e-result.json"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
DEBUG_PORT = 9333
APP_URL = "http://localhost:8530/?space=script"


async def run_cdp(websocket_url: str) -> dict[str, Any]:
    next_id = 0
    events: list[dict[str, Any]] = []

    async with websockets.connect(websocket_url, max_size=20_000_000) as socket:
        async def command(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            nonlocal next_id
            next_id += 1
            command_id = next_id
            await socket.send(json.dumps({"id": command_id, "method": method, "params": params or {}}))
            while True:
                message = json.loads(await socket.recv())
                if message.get("id") == command_id:
                    if "error" in message:
                        raise RuntimeError(f"CDP {method} failed: {message['error']}")
                    return message.get("result", {})
                events.append(message)

        async def evaluate(expression: str) -> Any:
            result = await command(
                "Runtime.evaluate",
                {"expression": expression, "returnByValue": True, "awaitPromise": True},
            )
            return result.get("result", {}).get("value")

        async def wait_for_text(fragment: str, timeout: float) -> str:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                body = str(await evaluate("document.body?.innerText || ''"))
                if fragment in body:
                    return body
                await asyncio.sleep(0.5)
            body = str(await evaluate("document.body?.innerText || ''"))
            raise TimeoutError(f"Timed out waiting for {fragment!r}. Body tail: {body[-1200:]}")

        await command("Runtime.enable")
        await command("Page.enable")
        await command("Log.enable")
        await command("Emulation.setDeviceMetricsOverride", {"width": 1600, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        await command("Page.navigate", {"url": APP_URL})
        await wait_for_text("今天想创作什么", 30)

        page_meta = await evaluate(
            "({lang:document.documentElement.lang,translate:document.documentElement.getAttribute('translate'),"
            "notranslate:document.documentElement.classList.contains('notranslate')})"
        )
        inserted = await evaluate(
            "(() => { const el=document.querySelector('textarea[data-testid=\"stChatInputTextArea\"]') || "
            "document.querySelector('[data-testid=\"stChatInput\"] textarea') || "
            "[...document.querySelectorAll('textarea')].at(-1); if(!el) return false; el.focus(); return true; })()"
        )
        if not inserted:
            raise RuntimeError("Chat input textarea was not found.")
        await command("Input.insertText", {"text": "请为中国剪纸制作一条面向初次接触非遗人群的45秒小红书科普内容"})
        await command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
        await command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})

        body = await wait_for_text("本次创作判断", 360)
        await evaluate(
            "(() => { const tab=[...document.querySelectorAll('[role=\"tab\"]')].find(x=>x.textContent.includes('知识与 Run'));"
            " if(tab){tab.click();return true;} return false; })()"
        )
        await asyncio.sleep(1)
        body = str(await evaluate("document.body?.innerText || ''"))
        await command("Page.bringToFront")
        shot = await command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True, "fromSurface": True})
        SCREENSHOT.write_bytes(base64.b64decode(shot["data"]))

        exception_events = [
            event for event in events
            if event.get("method") in {"Runtime.exceptionThrown", "Log.entryAdded"}
        ]
        return {
            "page_meta": page_meta,
            "has_remove_child": "removeChild" in body,
            "has_generation": "本次创作判断" in body,
            "has_request_id": "请求 ID" in body,
            "has_deepseek": "deepseek" in body.lower(),
            "exceptions": exception_events,
            "screenshot": str(SCREENSHOT),
            "body_tail": body[-1800:],
        }


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    PROFILE.mkdir(exist_ok=True)
    process = subprocess.Popen(
        [
            str(CHROME),
            "--headless=new",
            f"--remote-debugging-port={DEBUG_PORT}",
            "--remote-allow-origins=*",
            f"--user-data-dir={PROFILE}",
            "--disable-extensions",
            "--disable-translate",
            "--no-first-run",
            "--no-default-browser-check",
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
            raise RuntimeError("Chrome DevTools endpoint did not start.")
        result = asyncio.run(run_cdp(str(target["webSocketDebuggerUrl"])))
        REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=True, indent=2))
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    main()
