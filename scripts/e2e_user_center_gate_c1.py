"""Real Chrome acceptance for the durable G1 user center."""

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
ARTIFACTS = ROOT / "artifacts" / "e2e" / "user-center-g1"
WEB_URL = os.getenv("HAHA_E2E_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
DEBUG_PORT = int(os.getenv("HAHA_USER_CENTER_E2E_DEBUG_PORT", "9354"))
HEADERS = {"X-User-ID": f"g1-browser-{int(time.time())}", "X-Workspace-ID": "g1-browser"}


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


async def run(websocket_url: str) -> dict[str, Any]:
    command_id = 0
    events: list[dict[str, Any]] = []
    screenshots: list[str] = []
    viewports: list[dict[str, Any]] = []
    assertions: dict[str, bool] = {}
    async with websockets.connect(websocket_url, max_size=30_000_000) as socket:
        async def command(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            nonlocal command_id
            command_id += 1
            current = command_id
            await socket.send(json.dumps({"id": current, "method": method, "params": params or {}}))
            while True:
                message = json.loads(await asyncio.wait_for(socket.recv(), timeout=25))
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

        async def wait_for(text: str, timeout: float = 25) -> str:
            deadline = time.monotonic() + timeout
            body = ""
            while time.monotonic() < deadline:
                body = str(await evaluate("document.body?.innerText || ''"))
                if text in body:
                    return body
                await asyncio.sleep(0.25)
            raise TimeoutError(f"Timed out waiting for {text!r}: {body[-800:]}")

        async def navigate(path: str, expected: str) -> str:
            await command("Page.navigate", {"url": f"{WEB_URL}{path}"})
            return await wait_for(expected)

        async def wait_selector(selector: str, timeout: float = 25) -> None:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if await evaluate(f"Boolean(document.querySelector({json.dumps(selector)}))"):
                    return
                await asyncio.sleep(0.25)
            raise TimeoutError(f"Timed out waiting for selector {selector!r}")

        async def click(text: str) -> bool:
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                clicked = bool(await evaluate(f"""(() => {{const text={json.dumps(text)}; const node=[...document.querySelectorAll('button,a')].find(el=>(el.innerText||'').trim().includes(text)&&!el.disabled); if(!node)return false; node.click(); return true;}})()"""))
                if clicked:
                    return True
                await asyncio.sleep(0.25)
            return False

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
            body = await navigate("/identity", "今天从这里继续")
            metrics = await evaluate("({viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth,nav:[...document.querySelectorAll('.identityViewNav button')].map(x=>x.innerText)})")
            checks = {"loaded": "今天从这里继续" in body, "five_views": len(metrics["nav"]) == 5, "no_overflow": metrics["scrollWidth"] <= metrics["viewport"] + 1}
            if not all(checks.values()):
                raise RuntimeError(f"Viewport {width} failed: {checks} {metrics}")
            await shot(f"user-center-{width}.png")
            viewports.append({"width": width, "checks": checks, "metrics": metrics})

        await command("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        await command("Page.navigate", {"url": f"{WEB_URL}/content/content-embroidery-01"})
        await wait_selector(".productDetailGrid")
        for label in ("收藏", "想学", "稍后看"):
            assertions[f"{label}_clicked"] = await click(label)
            await asyncio.sleep(1.2)
        await navigate("/identity", "今天从这里继续")
        assertions["archive_opened"] = await click("文化资产")
        body = await wait_for("收藏、想学与稍后看已保存到服务端")
        assertions["assets_restored"] = int(await evaluate("document.querySelectorAll('.identityTaskList li').length")) >= 3
        assertions["history_restored"] = "观看记录" in body

        assertions["settings_opened"] = await click("设置")
        await wait_for("账户资料与隐私")
        await evaluate("""(() => {const values=['真实浏览器体验员','贵州','G1 跨设备文化账户']; const nodes=[...document.querySelectorAll('.identitySettingsForm input:not([type=checkbox]),.identitySettingsForm textarea')]; nodes.forEach((node,i)=>{const p=node.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(p,'value').set.call(node,values[i]||''); node.dispatchEvent(new Event('input',{bubbles:true}));}); return nodes.length;})()""")
        assertions["profile_submitted"] = await click("保存账户资料")
        await wait_for("账户资料已保存")
        await command("Page.reload")
        body = await wait_for("真实浏览器体验员的文化账户")
        assertions["profile_persisted"] = "贵州" in body

        assertions["inbox_opened"] = await click("消息与任务")
        await wait_for("系统消息与身份任务")
        if "标记已读" in str(await evaluate("document.body.innerText")):
            assertions["notification_read"] = await click("标记已读")
            await wait_for("消息已读")
        else:
            assertions["notification_read"] = True
        await shot("user-center-final.png")
        browser_errors = [item for item in events if item.get("method") in {"Runtime.exceptionThrown", "Log.entryAdded"}]
        assertions["no_browser_exceptions"] = not browser_errors
        if not all(assertions.values()):
            raise RuntimeError(f"G1 assertions failed: { {k:v for k,v in assertions.items() if not v} }")
        return {"status": "passed", "user": HEADERS["X-User-ID"], "viewports": viewports, "assertions": assertions, "browser_errors": len(browser_errors), "screenshots": screenshots}


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="haha-g1-e2e-") as profile:
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
