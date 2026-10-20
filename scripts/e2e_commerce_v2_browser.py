"""Real Chromium acceptance for the commerce v2 buyer and advisor experience."""

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
ARTIFACTS = ROOT / "artifacts" / "e2e" / "commerce-v2-browser"
WEB_URL = os.getenv("HAHA_E2E_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
DEBUG_PORT = int(os.getenv("HAHA_COMMERCE_V2_DEBUG_PORT", "9372"))


def find_chrome() -> Path:
    for candidate in (
        os.getenv("HAHA_E2E_CHROME", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    resolved = shutil.which("google-chrome") or shutil.which("chromium")
    if resolved:
        return Path(resolved)
    raise RuntimeError("Chrome or Chromium was not found")


async def run(websocket_url: str) -> dict[str, Any]:
    command_id = 0
    events: list[dict[str, Any]] = []
    assertions: dict[str, bool] = {}
    screenshots: list[str] = []
    headers = {"X-User-ID": "commerce-v2-browser", "X-Workspace-ID": "default"}
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

        async def shot(name: str) -> None:
            result = await command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
            path = ARTIFACTS / name
            path.write_bytes(base64.b64decode(result["data"]))
            screenshots.append(str(path))

        await command("Runtime.enable")
        await command("Page.enable")
        await command("Network.enable")
        await command("Network.setExtraHTTPHeaders", {"headers": headers})
        for width in (390, 768, 1440):
            await command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width <= 768})
            await command("Page.navigate", {"url": f"{WEB_URL}/commerce"})
            body = await wait_for("发现值得带回家的非遗好物")
            metrics = await evaluate("({viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth})")
            assertions[f"home_{width}_buyer_layout"] = "逛非遗好物" in body and "商品审核" not in body
            assertions[f"home_{width}_no_overflow"] = metrics["scrollWidth"] <= metrics["viewport"] + 1
            await shot(f"commerce-home-{width}.png")

        await command("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 950, "deviceScaleFactor": 1, "mobile": False})
        await command("Page.navigate", {"url": f"{WEB_URL}/commerce/advisor"})
        body = await wait_for("真实模型已连接")
        assertions["advisor_boundaries_visible"] = "不会代你下单或付款" in body and "仅建议，不执行交易" in body
        assertions["advisor_input_enabled"] = bool(await evaluate("!document.querySelector('#advisor-question')?.disabled"))
        await evaluate("""(() => {const node=document.querySelector('#advisor-question');const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;setter.call(node,'想找一件适合日常使用的礼物');node.dispatchEvent(new Event('input',{bubbles:true}));return true;})()""")
        await evaluate("document.querySelector('.commerceAdvisorComposer')?.requestSubmit()")
        body = await wait_for("当前目录还没有可售商品")
        assertions["empty_catalog_fail_closed"] = "不会虚构推荐" in body and "未调用模型" in body
        await command("Page.reload")
        body = await wait_for("当前目录还没有可售商品")
        assertions["advisor_history_persisted"] = "想找一件适合日常使用的礼物" in body
        await shot("commerce-advisor-persisted.png")
        browser_errors = [item for item in events if item.get("method") in {"Runtime.exceptionThrown", "Log.entryAdded"}]
        assertions["no_browser_exceptions"] = not browser_errors
        if not all(assertions.values()):
            raise RuntimeError({key: value for key, value in assertions.items() if not value})
        return {"status": "passed", "assertions": assertions, "browser_errors": len(browser_errors), "screenshots": screenshots}


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="haha-commerce-v2-", ignore_cleanup_errors=True) as profile:
        process = subprocess.Popen(
            [str(find_chrome()), "--headless=new", f"--remote-debugging-port={DEBUG_PORT}", "--remote-allow-origins=*", f"--user-data-dir={profile}", "--disable-extensions", "--no-first-run", "--hide-scrollbars", "about:blank"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
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
            print(json.dumps({"status": report["status"], "checks": len(report["assertions"])}, ensure_ascii=False))
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
