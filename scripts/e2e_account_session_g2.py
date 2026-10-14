"""Real JWT/PostgreSQL/Chrome acceptance for Account Session Gate G2."""

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
ARTIFACTS = ROOT / "artifacts" / "e2e" / "account-session-g2"
WEB_URL = os.getenv("HAHA_E2E_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
API_URL = os.getenv("HAHA_E2E_API_URL", "http://127.0.0.1:8000").rstrip("/")
DEBUG_PORT = int(os.getenv("HAHA_AUTH_E2E_DEBUG_PORT", "9356"))
EMAIL = os.getenv("HAHA_G2_E2E_EMAIL", "g2-e2e@haha.local")
WORKSPACE = os.getenv("HAHA_G2_E2E_WORKSPACE", "g2-e2e")
PASSWORD = os.getenv("HAHA_G2_E2E_PASSWORD", "")


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
    viewports: list[dict[str, Any]] = []
    screenshots: list[str] = []

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
            result = await command("Runtime.evaluate", {
                "expression": expression, "returnByValue": True, "awaitPromise": True,
            })
            if result.get("exceptionDetails"):
                raise RuntimeError(result["exceptionDetails"])
            return result.get("result", {}).get("value")

        async def wait_for(fragment: str, timeout: float = 25) -> str:
            deadline = time.monotonic() + timeout
            body = ""
            while time.monotonic() < deadline:
                body = str(await evaluate("document.body?.innerText || ''"))
                if fragment in body:
                    return body
                await asyncio.sleep(0.25)
            raise TimeoutError(f"Timed out waiting for {fragment!r}; body tail: {body[-1000:]}")

        async def navigate(path: str, expected: str) -> str:
            await command("Page.navigate", {"url": f"{WEB_URL}{path}"})
            return await wait_for(expected)

        async def click(fragment: str) -> bool:
            return bool(await evaluate(f"""(() => {{
              const text={json.dumps(fragment)};
              const node=[...document.querySelectorAll('button,a')]
                .find((item)=>(item.innerText||'').includes(text)&&!item.disabled);
              if(!node) return false; node.click(); return true;
            }})()"""))

        async def fill(selector: str, value: str) -> None:
            changed = await evaluate(f"""(() => {{
              const node=document.querySelector({json.dumps(selector)});
              if(!node) return false;
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(node,{json.dumps(value)});
              node.dispatchEvent(new Event('input',{{bubbles:true}})); return true;
            }})()""")
            if not changed:
                raise RuntimeError(f"Input not found: {selector}")

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
        for width in (390, 768, 1440):
            await command("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width <= 768,
            })
            body = await navigate("/login", "登录你的 HAHA 文化账户")
            metrics = await evaluate("({viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth})")
            checks = {
                "form_visible": "安全登录" in body,
                "no_overflow": metrics["scrollWidth"] <= metrics["viewport"] + 1,
            }
            if not all(checks.values()):
                raise RuntimeError(f"Login viewport {width} failed: {checks} {metrics}")
            viewports.append({"width": width, "checks": checks, "metrics": metrics})
            await shot(f"login-{width}.png")

        await command("Emulation.setDeviceMetricsOverride", {
            "width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False,
        })
        await navigate("/identity", "请先登录文化账户")
        assertions["protected_center_guides_to_login"] = await click("前往登录")
        await wait_for("登录你的 HAHA 文化账户")

        await fill("input[type=email]", EMAIL)
        await fill("input[autocomplete=organization]", WORKSPACE)
        await fill("input[type=password]", PASSWORD)
        assertions["login_submitted"] = await click("安全登录")
        await wait_for("今天从这里继续")
        token_state = await evaluate("({access:Boolean(sessionStorage.getItem('haha_access_token')),refresh:Boolean(sessionStorage.getItem('haha_refresh_token'))})")
        assertions["session_stored_in_tab"] = bool(token_state["access"] and token_state["refresh"])
        await shot("authenticated-user-center.png")

        old_refresh = await evaluate("sessionStorage.getItem('haha_refresh_token')")
        await evaluate("sessionStorage.setItem('haha_access_token','invalid-access-token')")
        await command("Page.reload")
        await wait_for("今天从这里继续")
        rotated = await evaluate("({access:sessionStorage.getItem('haha_access_token'),refresh:sessionStorage.getItem('haha_refresh_token')})")
        assertions["expired_access_auto_recovers"] = rotated["access"] != "invalid-access-token"
        assertions["refresh_token_rotated"] = bool(rotated["refresh"] and rotated["refresh"] != old_refresh)

        active_refresh = rotated["refresh"]
        await navigate("/login", "当前标签页已有登录会话")
        assertions["logout_submitted"] = await click("退出当前会话")
        await wait_for("登录你的 HAHA 文化账户")
        cleared = await evaluate("!sessionStorage.getItem('haha_access_token')&&!sessionStorage.getItem('haha_refresh_token')")
        assertions["browser_session_cleared"] = bool(cleared)
        refresh_body = json.dumps({"refresh_token": active_refresh})
        revoked_status = await evaluate(f"""fetch(
          {json.dumps(API_URL + '/api/auth/refresh')},
          {{method:'POST',headers:{{'Content-Type':'application/json'}},body:{json.dumps(refresh_body)}}}
        ).then((response)=>response.status)""")
        assertions["server_refresh_revoked"] = revoked_status == 401

        await fill("input[type=email]", EMAIL)
        await fill("input[autocomplete=organization]", WORKSPACE)
        await fill("input[type=password]", "deliberately-wrong-password")
        await click("安全登录")
        body = await wait_for("邮箱、密码或工作空间不正确")
        assertions["generic_invalid_login_error"] = "邮箱、密码或工作空间不正确" in body
        await shot("invalid-login.png")

        browser_errors = [
            item
            for item in events
            if item.get("method") == "Runtime.exceptionThrown"
            or (
                item.get("method") == "Log.entryAdded"
                and item.get("params", {}).get("entry", {}).get("source") == "javascript"
                and item.get("params", {}).get("entry", {}).get("level") == "error"
            )
        ]
        assertions["no_browser_exceptions"] = not browser_errors
        if not all(assertions.values()):
            details = [item.get("params", {}) for item in browser_errors[:3]]
            raise RuntimeError(
                f"G2 assertions failed: { {k: v for k, v in assertions.items() if not v} }; "
                f"browser errors: {json.dumps(details, ensure_ascii=False)[:3000]}"
            )
        return {
            "status": "passed",
            "viewports": viewports,
            "assertions": assertions,
            "browser_errors": len(browser_errors),
            "screenshots": screenshots,
        }


def main() -> None:
    if not PASSWORD:
        raise SystemExit("HAHA_G2_E2E_PASSWORD is required and is never stored in evidence")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="haha-g2-auth-e2e-") as profile:
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
                        urllib.request.Request(endpoint, method="PUT"), timeout=2,
                    ) as response:
                        target = json.load(response)
                    break
                except OSError:
                    time.sleep(0.15)
            if not target:
                raise RuntimeError("Chrome debug endpoint did not start")
            report = asyncio.run(run(target["webSocketDebuggerUrl"]))
            (ARTIFACTS / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
