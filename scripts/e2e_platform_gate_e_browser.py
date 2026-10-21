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


def prepare_account() -> None:
    request = urllib.request.Request(
        f"{API_URL}/api/identity/me",
        headers=HEADERS,
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"Account preparation failed: {response.status}")


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

        async def wait_for_value(expression: str, expected: Any, timeout: float = 30) -> Any:
            deadline = time.monotonic() + timeout
            value = None
            while time.monotonic() < deadline:
                value = await evaluate(expression)
                if value == expected:
                    return value
                await asyncio.sleep(0.25)
            raise TimeoutError(f"Timed out waiting for {expected!r}; last value was {value!r}")

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
            body = await wait_for("一个账户连接观看、学习、收藏与购物")
            metrics = await evaluate("""(() => ({
              viewport: innerWidth,
              scrollWidth: document.documentElement.scrollWidth,
              desktopModules: [...document.querySelectorAll('.productPrimaryNav a')].map(node => node.textContent.trim()),
              activeDesktop: document.querySelectorAll('.productPrimaryNav a[aria-current="page"]').length,
              mobileModules: [...document.querySelectorAll('.productMobileNav a')].map(node => node.textContent.trim()),
              platformCards: document.querySelectorAll('.platformModuleCard').length
            }))()""")
            checks = {
                "loaded_real_summary": "一个账户连接观看、学习、收藏与购物" in body,
                "no_overflow": metrics["scrollWidth"] <= metrics["viewport"] + 1,
                "desktop_four_modules": metrics["desktopModules"] == ["视频社区", "非遗电商", "AI 学习", "用户中心"],
                "neutral_home_has_no_active_module": metrics["activeDesktop"] == 0,
                "four_platform_cards": metrics["platformCards"] == 4,
                "mobile_five_entries": width > 768 or metrics["mobileModules"] == ["首页", "社区", "学习", "电商", "我的"],
                "honest_boundaries": (
                    "AI 非遗老师 · 受控能力" in body
                    and ("AI 老师可用" in body or "AI 老师受阻" in body)
                    and "INTERNAL SANDBOX" in body
                ),
                "professional_workbench_only": "浏览、学习与购物不需要切换身份" in body and not await evaluate("Boolean(document.querySelector('[data-testid=identity-conversion-guide] button'))"),
            }
            if not all(checks.values()):
                raise RuntimeError({"viewport": width, "checks": checks, "metrics": metrics})
            await shot(f"platform-home-{width}.png")
            viewports.append({"width": width, "checks": checks, "metrics": metrics})

        await command("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        search_scope = await evaluate("""(() => ({
          placeholder: document.querySelector('#product-global-search')?.getAttribute('placeholder'),
          label: document.querySelector('label[for="product-global-search"]')?.textContent.trim()
        }))()""")
        assertions["global_search_scope_is_honest"] = search_scope == {
            "placeholder": "搜索非遗内容、项目、人物和地区",
            "label": "搜索非遗内容、项目、人物和地区",
        }
        submitted = await evaluate("""(async () => {
          const input = document.querySelector('#product-global-search');
          const form = document.querySelector('.productSearch');
          if (!(input instanceof HTMLInputElement) || !(form instanceof HTMLFormElement)) return false;
          const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
          setter?.call(input, '苗绣');
          input.dispatchEvent(new Event('input', { bubbles: true }));
          await new Promise(resolve => setTimeout(resolve, 0));
          form.requestSubmit();
          return true;
        })()""")
        if not submitted:
            raise RuntimeError("Global search form was not available")
        await wait_for("搜索与发现")
        search_state = await evaluate("({path: location.pathname, query: new URLSearchParams(location.search).get('q')})")
        assertions["global_search_uses_expected_route"] = search_state == {"path": "/search", "query": "苗绣"}

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
        assertions["learning_route_and_boundary"] = (
            (
                "GROUNDED AI TUTOR" in body
                and "AI 非遗老师" in body
                and "BLOCKED" not in body
            )
            or (
                "BLOCKED" in body
                and "AI 非遗老师尚未接通" in body
                and "真实 DeepSeek 模型凭据" in body
            )
        )
        active_learning = await evaluate("document.querySelector('.productPrimaryNav a[aria-current=\"page\"]')?.textContent.trim()")
        assertions["learning_nav_active"] = active_learning == "AI 学习"

        body = await navigate("/commerce", "HAHA HERITAGE MARKET")
        assertions["commerce_route_and_boundary"] = (
            "INTERNAL SANDBOX" in body
            and "真实资金" in body
            and "BLOCKED" in body
        )
        active_commerce = await evaluate("document.querySelector('.productPrimaryNav a[aria-current=\"page\"]')?.textContent.trim()")
        assertions["commerce_nav_active"] = active_commerce == "非遗电商"

        await navigate("/identity?manage=roles", "普通功能不需要切换身份")
        identity_state = await evaluate("""(() => ({
          active: document.querySelector('.productPrimaryNav a[aria-current="page"]')?.textContent.trim(),
          duplicateCards: document.querySelectorAll('.platformModuleCard').length,
          accountName: document.querySelector('.productIdentityCopy strong')?.textContent.trim(),
          managerOpen: Boolean(document.querySelector('[data-testid="identity-manager"]')),
          separatesPermissions: document.querySelector('[data-testid="identity-manager"]')?.innerText.includes('内部权限不会出现在这里')
        }))()""")
        assertions["identity_is_distinct_not_duplicate_home"] = identity_state["active"] == "用户中心" and identity_state["duplicateCards"] == 0
        assertions["header_displays_account_not_role"] = bool(identity_state["accountName"])
        assertions["identity_center_is_primary_management_entry"] = identity_state["managerOpen"] and identity_state["separatesPermissions"]
        await shot("identity-manager.png")

        await click_selector('.identityActionGrid button[data-role="creator"]')
        confirmation = await evaluate("""(() => ({
          open: Boolean(document.querySelector('[role="alertdialog"]')),
          text: document.querySelector('[role="alertdialog"]')?.innerText || '',
          managerStillOpen: Boolean(document.querySelector('[data-testid="identity-manager"]'))
        }))()""")
        assertions["self_activation_requires_confirmation"] = confirmation["open"] and "确认开通" in confirmation["text"] and confirmation["managerStillOpen"]
        await shot("identity-activation-confirm.png")
        await click_selector('.productConfirmActions .productButtonSecondary')
        await click_selector('.identityDialogClose')

        await click_selector(".productIdentityTrigger")
        menu_state = await evaluate("""(() => ({
          open: document.querySelector('.productIdentityTrigger')?.getAttribute('aria-expanded'),
          labels: [...document.querySelectorAll('.productIdentityPopover a')].map(node => node.textContent.trim()),
          hint: document.querySelector('.productIdentityPopoverHint')?.innerText || '',
          hrefs: [...document.querySelectorAll('.productIdentityPopover a')].map(node => node.getAttribute('href'))
        }))()""")
        assertions["account_menu_discoverable"] = (
            menu_state["open"] == "true"
            and "用户中心" in menu_state["labels"]
            and "专业工作台" in menu_state["labels"]
            and "专业工作台" in menu_state["hint"]
            and "/identity?manage=roles" in menu_state["hrefs"]
        )
        await shot("identity-menu.png")

        await command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape"})
        await command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape"})
        await wait_for_value("document.querySelector('.productIdentityTrigger')?.getAttribute('aria-expanded')", "false")
        await wait_for_value("document.activeElement?.classList.contains('productIdentityTrigger')", True)
        assertions["identity_menu_escape_restores_focus"] = True

        await click_selector(".productIdentityTrigger")
        ordinary_switches = await evaluate(
            "document.querySelectorAll('.productIdentityPopover button[data-role=viewer],.productIdentityPopover button[data-role=learner],.productIdentityPopover button[data-role=buyer]').length"
        )
        assertions["ordinary_role_switches_are_absent"] = ordinary_switches == 0

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
    prepare_account()
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
