"""Real PostgreSQL/API/browser acceptance for the HAHA identity center."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import websockets

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "e2e" / "identity-center"
REPORT = ARTIFACTS / "report.json"
WEB_URL = os.getenv("HAHA_E2E_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
API_URL = os.getenv("HAHA_E2E_API_URL", "http://127.0.0.1:8000").rstrip("/")
DEBUG_PORT = int(os.getenv("HAHA_IDENTITY_E2E_DEBUG_PORT", "9352"))
APPLICANT_HEADERS = {"X-User-ID": "identity-e2e-user", "X-Workspace-ID": "identity-e2e"}
REVIEWER_HEADERS = {"X-User-ID": "identity-e2e-reviewer", "X-Workspace-ID": "identity-e2e"}


def find_chrome() -> Path:
    candidates = [
        os.getenv("HAHA_E2E_CHROME", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    for executable in ("google-chrome", "chromium", "chromium-browser", "msedge"):
        resolved = shutil.which(executable)
        if resolved:
            return Path(resolved)
    raise RuntimeError("Could not locate Chrome, Chromium, or Edge")


def api(path: str, *, method: str = "GET", headers: dict[str, str] | None = None, payload: dict[str, object] | None = None) -> tuple[int, dict[str, Any]]:
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(
        f"{API_URL}{path}", method=method, headers=request_headers,
        data=json.dumps(payload).encode() if payload is not None else None,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


async def run(websocket_url: str) -> dict[str, Any]:
    command_id = 0
    events: list[dict[str, Any]] = []
    assertions: dict[str, bool] = {}
    viewport_results: list[dict[str, Any]] = []

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

        async def wait_for(fragment: str, timeout: float = 25) -> str:
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

        async def click_text(text: str) -> bool:
            return bool(await evaluate(f"""(() => {{
              const text={json.dumps(text)};
              const el=[...document.querySelectorAll('button,a')].find(node=>(node.innerText||'').trim().includes(text)&&!node.disabled);
              if(!el)return false; el.click(); return true;
            }})()"""))

        async def click_in_card(title: str, action: str) -> bool:
            return bool(await evaluate(f"""(() => {{
              const title={json.dumps(title)}, action={json.dumps(action)};
              const card=[...document.querySelectorAll('article')].find(node=>(node.querySelector('h3')?.innerText||'').trim()===title);
              const button=card&&[...card.querySelectorAll('button,a')].find(node=>(node.innerText||'').includes(action)&&!node.disabled);
              if(!button)return false; button.click(); return true;
            }})()"""))

        async def screenshot(name: str) -> str:
            shot = await command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True, "fromSurface": True})
            path = ARTIFACTS / name
            path.write_bytes(base64.b64decode(shot["data"]))
            return str(path)

        await command("Runtime.enable")
        await command("Page.enable")
        await command("Log.enable")
        await command("Network.enable")
        await command("Network.setExtraHTTPHeaders", {"headers": APPLICANT_HEADERS})

        for width in (390, 768, 1440):
            await command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width <= 768})
            body = await navigate("/identity", "一个账户，多种文化身份")
            metrics = await evaluate("""(() => ({
              viewport: innerWidth,
              scrollWidth: document.documentElement.scrollWidth,
              overflow: Math.max(0,document.documentElement.scrollWidth-innerWidth),
              roles: document.querySelectorAll('.identityRoleGrid article').length
            }))()""")
            checks = {"loaded": "身份总览" in body, "roles": metrics["roles"] >= 2, "no_horizontal_overflow": metrics["overflow"] <= 1}
            if not all(checks.values()):
                raise RuntimeError(f"Identity viewport {width} failed: {checks}, {metrics}")
            viewport_results.append({"width": width, "metrics": metrics, "checks": checks, "screenshot": await screenshot(f"identity-{width}.png")})

        await command("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        status, initial = api("/api/identity/me", headers=APPLICANT_HEADERS)
        assertions["identity_api_ready"] = status == 200
        active_roles = {item["role"] for item in initial["roles"] if item["status"] == "active"}
        await navigate("/identity", "一个账户，多种文化身份")
        if "learner" not in active_roles:
            assertions["learner_activated_from_ui"] = await click_in_card("学习者", "开通身份")
            await wait_for("学习者工作台")
        else:
            assertions["learner_activated_from_ui"] = True

        if str(await evaluate("document.querySelector('.identityCurrentRole strong')?.innerText || ''")) != "学习者":
            assertions["learner_switched_from_ui"] = await click_in_card("学习者", "切换")
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if await evaluate("document.querySelector('.identityCurrentRole strong')?.innerText") == "学习者":
                    break
                await asyncio.sleep(0.25)
        else:
            assertions["learner_switched_from_ui"] = True
        assertions["learner_context_active"] = await evaluate("document.querySelector('.identityCurrentRole strong')?.innerText") == "学习者"
        await command("Page.reload")
        await wait_for("一个账户，多种文化身份")
        assertions["context_persisted_after_reload"] = await evaluate("document.querySelector('.identityCurrentRole strong')?.innerText") == "学习者"

        status, current = api("/api/identity/me", headers=APPLICANT_HEADERS)
        active_roles = {item["role"] for item in current["roles"] if item["status"] == "active"}
        if "seller" not in active_roles:
            pending = next((item for item in current["applications"] if item["role"] == "seller" and item["status"] == "pending"), None)
            if not pending:
                assertions["seller_application_opened"] = await click_in_card("卖家", "申请开通")
                await wait_for("申请卖家身份")
                await evaluate("""(() => {
                  const input=document.querySelector('.identityDialog textarea');
                  const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
                  setter.call(input,'计划经营经过授权的非遗作品并接受平台审核');
                  input.dispatchEvent(new Event('input',{bubbles:true}));
                  return input.value;
                })()""")
                assertions["seller_application_submitted"] = await click_text("提交审核")
                await wait_for("审核中")
                status, current = api("/api/identity/me", headers=APPLICANT_HEADERS)
                pending = next(item for item in current["applications"] if item["role"] == "seller" and item["status"] == "pending")
            else:
                assertions["seller_application_opened"] = True
                assertions["seller_application_submitted"] = True
            decision_status, _ = api(
                f"/api/identity/role-applications/{pending['id']}/decision", method="POST",
                headers=REVIEWER_HEADERS, payload={"decision": "approved", "note": "真实环境自动化审核通过"},
            )
            assertions["seller_approved_by_other_owner"] = decision_status == 200
        else:
            assertions["seller_application_opened"] = True
            assertions["seller_application_submitted"] = True
            assertions["seller_approved_by_other_owner"] = True

        await command("Page.reload")
        await wait_for("一个账户，多种文化身份")
        assertions["seller_grant_visible"] = "卖家" in str(await evaluate("document.body.innerText"))
        if await evaluate("document.querySelector('.identityCurrentRole strong')?.innerText") != "卖家":
            assertions["seller_switched_from_ui"] = await click_in_card("卖家", "切换")
            await asyncio.sleep(0.5)
        else:
            assertions["seller_switched_from_ui"] = True
        assertions["seller_context_active"] = await evaluate("document.querySelector('.identityCurrentRole strong')?.innerText") == "卖家"

        assertions["task_center_opened"] = await click_text("消息与任务")
        await wait_for("消息与任务中心")
        if "标记完成" in str(await evaluate("document.body.innerText")):
            assertions["task_completed_from_ui"] = await click_text("标记完成")
            await wait_for("已完成")
        else:
            assertions["task_completed_from_ui"] = True

        status, _ = api("/api/identity/context", method="POST", headers=APPLICANT_HEADERS, payload={"role": "admin"})
        assertions["forged_admin_context_rejected"] = status == 403
        status, contributor = api(
            "/api/identity/role-applications", method="POST", headers=APPLICANT_HEADERS,
            payload={"role": "contributor", "reason": "提交带有来源的文化知识并接受审核"},
        )
        if status == 201:
            self_status, _ = api(
                f"/api/identity/role-applications/{contributor['id']}/decision", method="POST",
                headers=APPLICANT_HEADERS, payload={"decision": "approved", "note": "self review"},
            )
            assertions["self_review_rejected"] = self_status == 403
        else:
            assertions["self_review_rejected"] = False

        await screenshot("identity-final.png")
        browser_errors = [event for event in events if event.get("method") in {"Runtime.exceptionThrown", "Log.entryAdded"}]
        failed_responses = [event for event in events if event.get("method") == "Network.responseReceived" and int(event.get("params", {}).get("response", {}).get("status", 0)) >= 400]
        assertions["no_browser_exceptions"] = not browser_errors
        assertions["no_failed_browser_responses"] = not failed_responses
        if not all(assertions.values()):
            raise RuntimeError(f"Identity assertions failed: { {key: value for key, value in assertions.items() if not value} }")
        return {
            "status": "passed", "web_url": WEB_URL, "api_url": API_URL,
            "viewports": viewport_results, "assertions": assertions,
            "browser_errors": len(browser_errors), "failed_browser_responses": len(failed_responses),
            "artifacts": [item["screenshot"] for item in viewport_results] + [str(ARTIFACTS / "identity-final.png")],
        }


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    chrome = find_chrome()
    with tempfile.TemporaryDirectory(prefix="haha-identity-e2e-") as profile:
        process = subprocess.Popen(
            [str(chrome), "--headless=new", f"--remote-debugging-port={DEBUG_PORT}", "--remote-allow-origins=*", f"--user-data-dir={profile}", "--disable-extensions", "--no-first-run", "--hide-scrollbars", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            endpoint = f"http://127.0.0.1:{DEBUG_PORT}/json/new?{urllib.parse.quote(WEB_URL, safe=':/?=&')}"
            target: dict[str, Any] | None = None
            for _ in range(100):
                try:
                    with urllib.request.urlopen(urllib.request.Request(endpoint, method="PUT"), timeout=2) as response:
                        target = json.load(response)
                    break
                except Exception:
                    time.sleep(0.2)
            if not target:
                raise RuntimeError("Chrome DevTools endpoint did not start")
            result = asyncio.run(asyncio.wait_for(run(str(target["webSocketDebuggerUrl"])), 150))
            REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False))
        except Exception as exc:
            REPORT.write_text(json.dumps({"status": "failed", "error": repr(exc)}, ensure_ascii=False, indent=2), encoding="utf-8")
            raise
        finally:
            process.terminate()
            process.wait(timeout=8)


if __name__ == "__main__":
    main()
