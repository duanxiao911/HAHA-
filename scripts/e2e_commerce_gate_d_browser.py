"""Real Chrome acceptance for the Gate D commerce sandbox UI."""

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
ARTIFACTS = ROOT / "artifacts" / "e2e" / "commerce-gate-d-browser"
API_STATE = ROOT / "artifacts" / "e2e" / "commerce-gate-d-api" / "state.json"
WEB_URL = os.getenv("HAHA_E2E_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
DEBUG_PORT = int(os.getenv("HAHA_D_E2E_DEBUG_PORT", "9364"))


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


async def run(websocket_url: str, headers: dict[str, str]) -> dict[str, Any]:
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
            raise TimeoutError(f"Timed out waiting for {text!r}: {body[-1500:]}")

        async def click(text: str) -> None:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                clicked = await evaluate(f"""(() => {{const target={json.dumps(text)};const node=[...document.querySelectorAll('button,a')].find(item=>!item.disabled&&(item.innerText||'').trim()===target);if(!node)return false;node.click();return true;}})()""")
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
        await command("Network.setExtraHTTPHeaders", {"headers": headers})
        for width in (390, 768, 1440):
            await command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width <= 768})
            await command("Page.navigate", {"url": f"{WEB_URL}/commerce"})
            body = await wait_for("非遗交易沙盒")
            metrics = await evaluate("({viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth})")
            checks = {
                "loaded": "不处理真实资金" in body and "单店结算" in body,
                "catalog_visible": "Gate D 来源待核验测试作品" in body,
                "no_overflow": metrics["scrollWidth"] <= metrics["viewport"] + 1,
            }
            if not all(checks.values()):
                raise RuntimeError({"viewport": width, "checks": checks, "metrics": metrics})
            await shot(f"commerce-{width}.png")
            viewports.append({"width": width, "checks": checks, "metrics": metrics})

        await command("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        await command("Page.navigate", {"url": f"{WEB_URL}/commerce"})
        await wait_for("加入购物车")
        await click("加入购物车")
        await wait_for("已加入购物车")
        await click("查看购物车")
        await wait_for("只支持单店商品一起结算")
        assertions["view_url_state"] = "view=cart" in str(await evaluate("location.search"))
        await click("结算")
        await wait_for("创建内部沙盒订单")
        await shot("commerce-checkout-confirm.png")
        await click("确认结算")
        await wait_for("确认结算已完成")
        await click("我的订单 1")
        await wait_for("沙盒支付")
        await click("沙盒支付")
        body = await wait_for("不会扣取真实资金")
        assertions["payment_confirmation"] = "银行卡" in body
        await click("确认沙盒支付")
        body = await wait_for("沙盒已支付")
        assertions["sandbox_paid_visible"] = "内部沙盒" in body and "不涉及真实资金" in body
        await command("Page.reload")
        body = await wait_for("沙盒已支付")
        assertions["refresh_restored_order"] = "Gate D 来源待核验测试作品" in body
        await shot("commerce-paid.png")
        browser_errors = [item for item in events if item.get("method") in {"Runtime.exceptionThrown", "Log.entryAdded"}]
        assertions["no_browser_exceptions"] = not browser_errors
        if not all(assertions.values()):
            raise RuntimeError({key: value for key, value in assertions.items() if not value})
        return {"status": "passed", "viewports": viewports, "assertions": assertions, "browser_errors": len(browser_errors), "screenshots": screenshots}


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    state = json.loads(API_STATE.read_text(encoding="utf-8"))
    headers = {"X-User-ID": f"browser-buyer-{uuid4().hex[:8]}", "X-Workspace-ID": state["workspace"]}
    with tempfile.TemporaryDirectory(prefix="haha-d-e2e-", ignore_cleanup_errors=True) as profile:
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
            report = asyncio.run(run(target["webSocketDebuggerUrl"], headers))
            (ARTIFACTS / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
