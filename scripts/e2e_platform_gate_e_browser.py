"""Real Chrome acceptance for Gate E unified platform navigation."""

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
ARTIFACTS = ROOT / "artifacts" / "e2e" / "platform-gate-e-browser"
WEB_URL = os.getenv("HAHA_E2E_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
API_URL = os.getenv("HAHA_E2E_API_URL", "http://127.0.0.1:8000").rstrip("/")
DEBUG_PORT = int(os.getenv("HAHA_E_E2E_DEBUG_PORT", "9365"))
SUFFIX = uuid4().hex[:10]
HEADERS = {"X-User-ID": f"gate-e-browser-{SUFFIX}", "X-Workspace-ID": f"gate-e-browser-{SUFFIX}"}


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
    request = urllib.request.Request(
        f"{API_URL}/api/identity/roles/learner/activate",
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"Learner activation failed: {response.status}")
    switch = urllib.request.Request(
        f"{API_URL}/api/identity/context",
        data=json.dumps({"role": "learner"}).encode("utf-8"),
        headers={**HEADERS, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(switch, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"Learner context switch failed: {response.status}")


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

        async def click_selector(selector: str) -> None:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                clicked = await evaluate(f"""(() => {{const node=document.querySelector({json.dumps(selector)});if(!node||node.disabled)return false;node.click();return true;}})()""")
                if clicked:
                    return
                await asyncio.sleep(0.25)
            raise TimeoutError(f"Could not click selector {selector!r}")

        async def navigate(path: str, ready_text: str) -> str:
            await command("Page.navigate", {"url": f"{WEB_URL}{path}"})
            return await wait_for(ready_text)

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
            await command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 920, "deviceScaleFactor": 1, "mobile": width <= 768})
            body = await navigate("/", "四大板块，一处进入")
            body = await wait_for("当前以“学习者”身份进入")
            metrics = await evaluate("""(() => ({
              viewport: innerWidth,
              scrollWidth: document.documentElement.scrollWidth,
              desktopModules: [...document.querySelectorAll('.productPrimaryNav a')].map(node => node.textContent.trim()),
              activeDesktop: document.querySelectorAll('.productPrimaryNav a[aria-current="page"]').length,
              mobileModules: [...document.querySelectorAll('.productMobileNav a')].map(node => node.textContent.trim()),
              platformCards: document.querySelectorAll('.platformModuleCard').length
            }))()""")
            checks = {
                "loaded_real_summary": "当前以“学习者”身份进入" in body,
                "no_overflow": metrics["scrollWidth"] <= metrics["viewport"] + 1,
                "desktop_four_modules": metrics["desktopModules"] == ["视频社区", "非遗电商", "AI 学习", "用户中心"],
                "neutral_home_has_no_active_module": metrics["activeDesktop"] == 0,
                "four_platform_cards": metrics["platformCards"] == 4,
                "mobile_five_entries": width > 768 or metrics["mobileModules"] == ["首页", "社区", "学习", "电商", "我的"],
                "honest_boundaries": "AI 非遗老师 · BLOCKED" in body and "INTERNAL SANDBOX" in body,
            }
            if not all(checks.values()):
                raise RuntimeError({"viewport": width, "checks": checks, "metrics": metrics})
            await shot(f"platform-home-{width}.png")
            viewports.append({"width": width, "checks": checks, "metrics": metrics})

        await command("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        await navigate("/community", "内容 Feed")
        community_shell = await evaluate("""(() => ({
          active: document.querySelector('.productPrimaryNav a[aria-current="page"]')?.textContent.trim(),
          sharedHeaders: document.querySelectorAll('.productHeader').length,
          legacyHeaders: document.querySelectorAll('.globalHeader').length,
          channels: document.querySelectorAll('.channelNavigation').length
        }))()""")
        assertions["community_uses_shared_shell"] = community_shell == {"active": "视频社区", "sharedHeaders": 1, "legacyHeaders": 0, "channels": 1}

        await navigate("/creator", "AI 创作工作区")
        creator_state = await evaluate("""(() => ({
          path: location.pathname,
          console: Boolean(document.querySelector('.controlConsole')),
          communityReturn: Boolean(document.querySelector('a[href="/community"]'))
        }))()""")
        assertions["creator_route_preserved_after_root_split"] = creator_state == {"path": "/creator", "console": True, "communityReturn": True}

        body = await navigate("/learning", "学习成长中心")
        assertions["learning_route_and_boundary"] = "AI 非遗老师尚未接通" in body and "BLOCKED" in body
        active_learning = await evaluate("document.querySelector('.productPrimaryNav a[aria-current=\"page\"]')?.textContent.trim()")
        assertions["learning_nav_active"] = active_learning == "AI 学习"

        body = await navigate("/commerce", "非遗交易沙盒")
        assertions["commerce_route_and_boundary"] = "INTERNAL SANDBOX" in body and "不处理真实资金" in body
        active_commerce = await evaluate("document.querySelector('.productPrimaryNav a[aria-current=\"page\"]')?.textContent.trim()")
        assertions["commerce_nav_active"] = active_commerce == "非遗电商"

        await navigate("/identity", "文化账户")
        identity_state = await evaluate("""(() => ({
          active: document.querySelector('.productPrimaryNav a[aria-current="page"]')?.textContent.trim(),
          duplicateCards: document.querySelectorAll('.platformModuleCard').length,
          currentRole: document.querySelector('.productIdentityCopy strong')?.textContent.trim()
        }))()""")
        assertions["identity_is_distinct_not_duplicate_home"] = identity_state["active"] == "用户中心" and identity_state["duplicateCards"] == 0
        assertions["header_displays_active_role"] = identity_state["currentRole"] == "学习者"

        await click_selector(".productIdentityTrigger")
        menu_state = await evaluate("""(() => ({
          open: document.querySelector('.productIdentityTrigger')?.getAttribute('aria-expanded'),
          labels: [...document.querySelectorAll('.productIdentityPopover button')].map(node => node.textContent.trim())
        }))()""")
        assertions["identity_menu_discoverable"] = menu_state["open"] == "true" and any("浏览者" in label for label in menu_state["labels"])
        await shot("identity-menu.png")

        browser_errors = [item for item in events if item.get("method") in {"Runtime.exceptionThrown", "Log.entryAdded"}]
        assertions["no_browser_exceptions"] = not browser_errors
        if not all(assertions.values()):
            raise RuntimeError({key: value for key, value in assertions.items() if not value})
        return {
            "status": "passed", "user": HEADERS["X-User-ID"], "viewports": viewports,
            "assertions": assertions, "browser_errors": len(browser_errors), "screenshots": screenshots,
        }


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    activate_learner()
    with tempfile.TemporaryDirectory(prefix="haha-gate-e-e2e-", ignore_cleanup_errors=True) as profile:
        process = subprocess.Popen(
            [str(find_chrome()), "--headless=new", f"--remote-debugging-port={DEBUG_PORT}", "--remote-allow-origins=*", f"--user-data-dir={profile}", "--disable-extensions", "--no-first-run", "--hide-scrollbars", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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
            print(json.dumps(report, ensure_ascii=False, indent=2))
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
