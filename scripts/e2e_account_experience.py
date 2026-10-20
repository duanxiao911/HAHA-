"""Real browser acceptance for public registration and account/workbench UX."""

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
ARTIFACTS = ROOT / "artifacts" / "e2e" / "account-experience"
WEB_URL = os.getenv("HAHA_E2E_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
DEBUG_PORT = int(os.getenv("HAHA_ACCOUNT_E2E_DEBUG_PORT", "9368"))
EMAIL = f"account-e2e-{uuid4().hex[:12]}@haha.local"
PASSWORD = "Account-E2E-Strong-Password-2026"


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


async def run(websocket_url: str) -> dict[str, Any]:
    command_id = 0
    events: list[dict[str, Any]] = []
    assertions: dict[str, bool] = {}
    screenshots: list[str] = []

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
            result = await command("Runtime.evaluate", {
                "expression": expression, "returnByValue": True, "awaitPromise": True,
            })
            if result.get("exceptionDetails"):
                raise RuntimeError(result["exceptionDetails"])
            return result.get("result", {}).get("value")

        async def wait_for(fragment: str, timeout: float = 30) -> str:
            deadline = time.monotonic() + timeout
            body = ""
            while time.monotonic() < deadline:
                body = str(await evaluate("document.body?.innerText || ''"))
                if fragment in body:
                    return body
                await asyncio.sleep(0.25)
            raise TimeoutError(f"Timed out waiting for {fragment!r}; body tail: {body[-1200:]}")

        async def navigate(path: str, expected: str) -> str:
            await command("Page.navigate", {"url": f"{WEB_URL}{path}"})
            return await wait_for(expected)

        async def fill(selector: str, value: str) -> None:
            changed = await evaluate(f"""(() => {{
              const node=document.querySelector({json.dumps(selector)});
              if(!(node instanceof HTMLInputElement)) return false;
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(node,{json.dumps(value)});
              node.dispatchEvent(new Event('input',{{bubbles:true}})); return true;
            }})()""")
            if not changed:
                raise RuntimeError(f"Input not found: {selector}")

        async def click(text: str) -> bool:
            return bool(await evaluate(f"""(() => {{
              const expected={json.dumps(text)};
              const nodes=[...document.querySelectorAll('button,a')].filter(node=>!node.disabled);
              const node=nodes.find(node=>(node.innerText||'').trim()===expected)
                ||nodes.find(node=>(node.innerText||'').includes(expected));
              if(!node) return false; node.click(); return true;
            }})()"""))

        async def click_in_article(heading: str, action: str) -> bool:
            return bool(await evaluate(f"""(() => {{
              const article=[...document.querySelectorAll('article')]
                .find(node=>(node.innerText||'').includes({json.dumps(heading)}));
              const button=article&&[...article.querySelectorAll('button')]
                .find(node=>(node.innerText||'').includes({json.dumps(action)})&&!node.disabled);
              if(!button) return false; button.click(); return true;
            }})()"""))

        async def shot(name: str) -> None:
            result = await command("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": True,
            })
            path = ARTIFACTS / name
            path.write_bytes(base64.b64decode(result["data"]))
            screenshots.append(str(path))

        await command("Runtime.enable")
        await command("Page.enable")
        await command("Network.enable")

        for width in (390, 1440):
            await command("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": 950, "deviceScaleFactor": 1, "mobile": width <= 768,
            })
            body = await navigate("/register", "创建文化账户")
            metrics = await evaluate(
                "({viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth,"
                "mobileNav:document.querySelectorAll('.productMobileNav').length})"
            )
            assertions[f"register_{width}_responsive"] = (
                metrics["scrollWidth"] <= metrics["viewport"] + 1
                and metrics["mobileNav"] == 0
                and "不需要预先选择身份" in body
                and "审核员和管理员属于平台内部权限" in body
            )
            await shot(f"register-{width}.png")

        await command("Emulation.setDeviceMetricsOverride", {
            "width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False,
        })
        await fill("input[autocomplete=nickname]", "非遗新朋友")
        await fill("input[type=email]", EMAIL)
        await fill("input[autocomplete=new-password]", PASSWORD)
        confirmation_filled = await evaluate(f"""(() => {{
          const nodes=[...document.querySelectorAll('input[autocomplete=new-password]')];
          if(nodes.length!==2) return false;
          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(nodes[1],{json.dumps(PASSWORD)});
          nodes[1].dispatchEvent(new Event('input',{{bubbles:true}})); return true;
        }})()""")
        if not confirmation_filled:
            raise RuntimeError("Password confirmation input was not found")
        assertions["registration_submitted"] = await click("创建账户")
        body = await wait_for("今天从这里继续")
        assertions["ordinary_capabilities_visible"] = (
            "看、学、买，不需要身份切换" in body
            and "学习成长" in body
            and "购物服务" in body
        )
        assertions["display_name_persisted"] = "非遗新朋友" in body
        cookies = (await command("Network.getAllCookies"))["cookies"]
        cookie_map = {item["name"]: item for item in cookies}
        assertions["registration_uses_http_only_session"] = all(
            cookie_map.get(name, {}).get("httpOnly") for name in ("haha_access", "haha_refresh")
        )
        await shot("registered-user-center.png")

        assertions["professional_manager_opened"] = await click("专业工作台")
        body = await wait_for("内部权限不会出现在这里")
        hidden_internal_actions = await evaluate(
            "document.querySelectorAll('button[data-role=reviewer],button[data-role=admin]').length"
        )
        assertions["internal_roles_are_not_public_actions"] = (
            hidden_internal_actions == 0
            and "公众账户不能申请或自行切换" in body
        )
        assertions["creator_activation_started"] = await click_in_article(
            "开通创作者工作台", "开始创作"
        )
        await wait_for("开通创作者工作台？")
        assertions["creator_activation_confirmed"] = await click("确认开通")
        await wait_for("创作者工作台已开通")
        assertions["creator_entered"] = await click_in_article("创作者工作台", "进入")
        await wait_for("已切换为创作者")
        assertions["workbench_opened"] = await click("进入专业工作台")
        await wait_for("ACTIVE ROLE WORKBENCH")
        await command("Page.reload")
        body = await wait_for("ACTIVE ROLE WORKBENCH")
        assertions["workbench_context_survives_refresh"] = "创作者工作台" in body
        await shot("creator-workbench-restored.png")

        browser_errors = [
            item for item in events
            if item.get("method") == "Runtime.exceptionThrown"
            or (
                item.get("method") == "Log.entryAdded"
                and item.get("params", {}).get("entry", {}).get("level") == "error"
            )
        ]
        assertions["no_browser_exceptions"] = not browser_errors
        if not all(assertions.values()):
            raise RuntimeError({key: value for key, value in assertions.items() if not value})
        return {
            "status": "passed",
            "email": EMAIL,
            "assertions": assertions,
            "screenshots": screenshots,
            "browser_errors": len(browser_errors),
        }


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="haha-account-e2e-", ignore_cleanup_errors=True) as profile:
        process = subprocess.Popen(
            [
                str(find_chrome()), "--headless=new", f"--remote-debugging-port={DEBUG_PORT}",
                "--remote-allow-origins=*", f"--user-data-dir={profile}", "--disable-extensions",
                "--no-first-run", "--hide-scrollbars", "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            endpoint = f"http://127.0.0.1:{DEBUG_PORT}/json/new?{urllib.parse.quote(WEB_URL, safe=':/?=&')}"
            target = None
            for _ in range(100):
                try:
                    with urllib.request.urlopen(
                        urllib.request.Request(endpoint, method="PUT"), timeout=2
                    ) as response:
                        target = json.load(response)
                    break
                except OSError:
                    time.sleep(0.15)
            if not target:
                raise RuntimeError("Chrome debug endpoint did not start")
            report = asyncio.run(run(target["webSocketDebuggerUrl"]))
            (ARTIFACTS / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
