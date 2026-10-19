"""Real Docker/PostgreSQL/Next.js/Chrome acceptance for Browser Session Gate G3."""

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
ARTIFACTS = ROOT / "artifacts" / "e2e" / "browser-session-g3"
WEB_URL = os.getenv("HAHA_E2E_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
DEBUG_PORT = int(os.getenv("HAHA_G3_E2E_DEBUG_PORT", "9363"))
EMAIL = os.getenv("HAHA_G3_E2E_EMAIL", "g3-e2e@haha.local")
WORKSPACE = os.getenv("HAHA_G3_E2E_WORKSPACE", "g3-e2e")
PASSWORD = os.getenv("HAHA_G3_E2E_PASSWORD", "")


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
    assertions: dict[str, bool] = {}
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
              const nodes=[...document.querySelectorAll('button,a')]
                .filter((item)=>!item.disabled);
              const node=nodes.find((item)=>(item.innerText||'').trim()===text)
                ||nodes.find((item)=>(item.innerText||'').includes(text));
              if(!node) return false; node.click(); return true;
            }})()"""))

        async def click_dialog(fragment: str) -> bool:
            return bool(await evaluate(f"""(() => {{
              const text={json.dumps(fragment)};
              const dialog=document.querySelector('[role=alertdialog]');
              if(!dialog) return false;
              const node=[...dialog.querySelectorAll('button')]
                .find((item)=>!item.disabled&&(item.innerText||'').trim()===text);
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

        browser_storage = await evaluate("""({
          session:[...Array(sessionStorage.length)].map((_,i)=>[sessionStorage.key(i),sessionStorage.getItem(sessionStorage.key(i))]),
          local:[...Array(localStorage.length)].map((_,i)=>[localStorage.key(i),localStorage.getItem(localStorage.key(i))]),
          visibleCookie:document.cookie
        })""")
        serialized_storage = json.dumps(browser_storage["session"] + browser_storage["local"])
        assertions["no_token_in_web_storage"] = all(
            marker not in serialized_storage.lower()
            for marker in ("access_token", "refresh_token", "haha_access", "haha_refresh")
        )
        assertions["only_csrf_cookie_visible_to_js"] = (
            "haha_csrf=" in browser_storage["visibleCookie"]
            and "haha_access=" not in browser_storage["visibleCookie"]
            and "haha_refresh=" not in browser_storage["visibleCookie"]
        )
        cookies = (await command("Network.getAllCookies"))["cookies"]
        cookie_map = {item["name"]: item for item in cookies if item.get("domain") in {"127.0.0.1", "localhost"}}
        assertions["access_cookie_is_http_only"] = bool(cookie_map.get("haha_access", {}).get("httpOnly"))
        assertions["refresh_cookie_is_http_only"] = bool(cookie_map.get("haha_refresh", {}).get("httpOnly"))
        assertions["session_cookies_are_same_site_lax"] = all(
            cookie_map.get(name, {}).get("sameSite") == "Lax"
            for name in ("haha_access", "haha_refresh")
        )

        missing_csrf = await evaluate("""fetch('/api/backend/api/user-center/preferences', {
          method:'PATCH', headers:{'Content-Type':'application/json'},
          body:JSON.stringify({history_enabled:true,recommendation_enabled:true,personalization_enabled:false,notification_enabled:true})
        }).then((response)=>response.status)""")
        assertions["mutation_without_csrf_rejected"] = missing_csrf == 403
        blocked_token_endpoint = await evaluate("""(() => {
          const csrf=document.cookie.split('; ').find((value)=>value.startsWith('haha_csrf='))?.split('=')[1]||'';
          return fetch('/api/backend/api/auth/refresh', {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':decodeURIComponent(csrf)},body:'{}'}).then((response)=>response.status);
        })()""")
        assertions["raw_token_endpoint_not_proxyable"] = blocked_token_endpoint == 404

        old_refresh = cookie_map["haha_refresh"]["value"]
        await command("Network.setCookie", {
            "name": "haha_access", "value": "invalid-access-token", "url": WEB_URL,
            "httpOnly": True, "sameSite": "Lax",
        })
        await command("Page.reload")
        await wait_for("今天从这里继续")
        rotated_cookies = (await command("Network.getAllCookies"))["cookies"]
        rotated_map = {item["name"]: item for item in rotated_cookies if item.get("domain") in {"127.0.0.1", "localhost"}}
        assertions["invalid_access_auto_recovers"] = rotated_map.get("haha_access", {}).get("value") not in {"", "invalid-access-token"}
        assertions["refresh_token_rotated_server_side"] = rotated_map.get("haha_refresh", {}).get("value") not in {"", old_refresh}

        assertions["settings_opened"] = await click("设置")
        await wait_for("登录设备与会话")
        body = await wait_for("当前会话")
        assertions["current_session_listed"] = "当前会话" in body and "有效" in body
        await shot("authenticated-session-settings.png")

        assertions["revoke_all_clicked"] = await click("退出全部设备")
        await wait_for("退出全部设备？")
        assertions["revoke_all_confirmed"] = await click_dialog("退出全部设备")
        await wait_for("登录你的 HAHA 文化账户")
        final_cookies = (await command("Network.getAllCookies"))["cookies"]
        final_names = {item["name"] for item in final_cookies if item.get("domain") in {"127.0.0.1", "localhost"}}
        assertions["credentials_cleared_after_revoke_all"] = not {"haha_access", "haha_refresh"}.intersection(final_names)

        login_contract = await evaluate(f"""fetch('/api/session/login', {{
          method:'POST',headers:{{'Content-Type':'application/json'}},
          body:JSON.stringify({{email:{json.dumps(EMAIL)},password:{json.dumps(PASSWORD)},workspace_id:{json.dumps(WORKSPACE)}}})
        }}).then(async (response)=>({{status:response.status,body:await response.json()}}))""")
        assertions["login_response_has_no_tokens"] = (
            login_contract["status"] == 200
            and "access_token" not in login_contract["body"]
            and "refresh_token" not in login_contract["body"]
            and login_contract["body"].get("authenticated") is True
        )
        logout_status = await evaluate("""(() => {
          const csrf=document.cookie.split('; ').find((value)=>value.startsWith('haha_csrf='))?.split('=')[1]||'';
          return fetch('/api/session/logout',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':decodeURIComponent(csrf)}}).then((response)=>response.status);
        })()""")
        assertions["final_logout_succeeds"] = logout_status == 204

        browser_errors = [
            item for item in events
            if item.get("method") == "Runtime.exceptionThrown"
            or (item.get("method") == "Log.entryAdded"
                and item.get("params", {}).get("entry", {}).get("level") == "error")
        ]
        assertions["no_browser_exceptions"] = not browser_errors
        if not all(assertions.values()):
            raise RuntimeError(f"G3 assertions failed: { {k: v for k, v in assertions.items() if not v} }")
        return {
            "status": "passed", "assertions": assertions,
            "browser_errors": len(browser_errors), "screenshots": screenshots,
        }


def main() -> None:
    if not PASSWORD:
        raise SystemExit("HAHA_G3_E2E_PASSWORD is required and is never stored in evidence")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    # Chromium can leave short-lived child processes writing profile files after the
    # parent exits on Linux CI. Ignore only profile cleanup races on the ephemeral
    # runner; browser assertions and process exit handling still fail normally.
    with tempfile.TemporaryDirectory(
        prefix="haha-g3-auth-e2e-", ignore_cleanup_errors=True
    ) as profile:
        process = subprocess.Popen([
            str(find_chrome()), "--headless=new", f"--remote-debugging-port={DEBUG_PORT}",
            "--remote-allow-origins=*", f"--user-data-dir={profile}", "--disable-extensions",
            "--no-first-run", "--hide-scrollbars", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
            (ARTIFACTS / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
