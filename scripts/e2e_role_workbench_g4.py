"""Real Docker/PostgreSQL/Next.js/Chrome acceptance for role workbench G4."""

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
ARTIFACTS = ROOT / "artifacts" / "e2e" / "role-workbench-g4"
WEB_URL = os.getenv("HAHA_E2E_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
DEBUG_PORT = int(os.getenv("HAHA_G4_E2E_DEBUG_PORT", "9364"))
EMAIL = os.getenv("HAHA_G4_E2E_EMAIL", "g4-e2e@haha.local")
WORKSPACE = os.getenv("HAHA_G4_E2E_WORKSPACE", "g4-e2e")
PASSWORD = os.getenv("HAHA_G4_E2E_PASSWORD", "")


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
                message = json.loads(await asyncio.wait_for(socket.recv(), timeout=25))
                if message.get("id") == current:
                    if "error" in message:
                        raise RuntimeError(message["error"])
                    return message.get("result", {})
                events.append(message)

        async def evaluate(expression: str) -> Any:
            result = await command(
                "Runtime.evaluate",
                {
                    "expression": expression,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            )
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

        async def click(fragment: str) -> bool:
            return bool(
                await evaluate(
                    f"""(() => {{
                      const text={json.dumps(fragment)};
                      const nodes=[...document.querySelectorAll('button,a')]
                        .filter((item)=>!item.disabled);
                      const node=nodes.find((item)=>(item.innerText||'').trim()===text)
                        ||nodes.find((item)=>(item.innerText||'').includes(text));
                      if(!node) return false; node.click(); return true;
                    }})()"""
                )
            )

        async def click_when_ready(fragment: str, timeout: float = 15) -> bool:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if await click(fragment):
                    return True
                await asyncio.sleep(0.25)
            return False

        async def click_in_article(article_text: str, button_text: str) -> bool:
            return bool(
                await evaluate(
                    f"""(() => {{
                      const article=[...document.querySelectorAll('article')]
                        .find((item)=>(item.innerText||'').includes({json.dumps(article_text)}));
                      const button=article&&[...article.querySelectorAll('button,a')]
                        .find((item)=>(item.innerText||'').includes({json.dumps(button_text)})&&!item.disabled);
                      if(!button) return false; button.click(); return true;
                    }})()"""
                )
            )

        async def click_in_article_when_ready(
            article_text: str, button_text: str, timeout: float = 15
        ) -> bool:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if await click_in_article(article_text, button_text):
                    return True
                await asyncio.sleep(0.25)
            return False

        async def click_in_confirmation(button_text: str) -> bool:
            return bool(
                await evaluate(
                    f"""(() => {{
                      const dialog=document.querySelector('[role=\"alertdialog\"]');
                      const button=dialog&&[...dialog.querySelectorAll('button')]
                        .find((item)=>(item.innerText||'').trim()==={json.dumps(button_text)}&&!item.disabled);
                      if(!button) return false; button.click(); return true;
                    }})()"""
                )
            )

        async def fill(selector: str, value: str) -> None:
            changed = await evaluate(
                f"""(() => {{
                  const node=document.querySelector({json.dumps(selector)});
                  if(!node) return false;
                  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(node,{json.dumps(value)});
                  node.dispatchEvent(new Event('input',{{bubbles:true}})); return true;
                }})()"""
            )
            if not changed:
                raise RuntimeError(f"Input not found: {selector}")

        async def api(path: str, init: str = "{}") -> dict[str, Any]:
            return await evaluate(
                f"""(() => {{
                  const csrf=document.cookie.split('; ').find((value)=>value.startsWith('haha_csrf='))?.split('=')[1]||'';
                  const extra={init};
                  return fetch({json.dumps(path)},{{...extra,headers:{{'Content-Type':'application/json','X-CSRF-Token':decodeURIComponent(csrf),...(extra.headers||{{}})}}}})
                    .then(async(response)=>({{status:response.status,body:await response.json().catch(()=>({{}}))}}));
                }})()"""
            )

        async def shot(name: str) -> None:
            result = await command(
                "Page.captureScreenshot",
                {"format": "png", "captureBeyondViewport": True},
            )
            path = ARTIFACTS / name
            path.write_bytes(base64.b64decode(result["data"]))
            screenshots.append(str(path))

        await command("Runtime.enable")
        await command("Page.enable")
        await command("Network.enable")
        await command(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False},
        )
        await command("Page.navigate", {"url": f"{WEB_URL}/identity"})
        await wait_for("请先登录文化账户")
        assertions["protected_entry"] = await click("前往登录")
        await wait_for("登录你的 HAHA 文化账户")
        await fill("input[type=email]", EMAIL)
        await fill("input[autocomplete=organization]", WORKSPACE)
        await fill("input[type=password]", PASSWORD)
        assertions["login"] = await click("安全登录")
        await wait_for("今天从这里继续")

        body = await wait_for("浏览者能力状态")
        assertions["viewer_context_on_today"] = "浏览者能力状态" in body
        assertions["viewer_boundary_visible"] = (
            "社区内容仍含本地适配数据" in body and "有限可用" in body
        )
        forged = await api("/api/backend/api/identity/workbench?role=admin")
        assertions["query_role_cannot_escalate"] = (
            forged["status"] == 200 and forged["body"].get("role") == "viewer"
        )

        assertions["role_menu_at_page_top"] = await click_when_ready("切换身份")
        await wait_for("管理与开通身份")
        assertions["identity_manager_opened"] = await click_when_ready(
            "管理与开通身份"
        )
        await wait_for("切换与开通是两件事")
        assertions["creator_activated"] = await click_in_article_when_ready(
            "开通创作者", "开通身份"
        )
        await wait_for("开通创作者身份？")
        assertions["creator_activation_confirmed"] = await click_in_confirmation(
            "确认开通"
        )
        await wait_for("创作者已开通")
        assertions["creator_switched"] = await click_in_article("创作者", "切换")
        await wait_for("创作者工作台")
        assertions["professional_workbench_entry"] = await click("创作者工作台")
        await wait_for("ACTIVE ROLE WORKBENCH")
        project = await api(
            "/api/backend/api/projects",
            "{method:'POST',body:JSON.stringify({title:'G4 真实浏览器创作项目'})}",
        )
        assertions["creator_project_created"] = project["status"] == 201
        await command("Page.reload")
        body = await wait_for("G4 真实浏览器创作项目")
        assertions["creator_project_restored"] = "创作项目" in body

        await click_when_ready("当前身份")
        await wait_for("管理与开通身份")
        await click_when_ready("管理与开通身份")
        await wait_for("切换与开通是两件事")
        assertions["learner_activated"] = await click_in_article_when_ready(
            "开通学习者", "开通身份"
        )
        await wait_for("开通学习者身份？")
        assertions["learner_activation_confirmed"] = await click_in_confirmation(
            "确认开通"
        )
        await wait_for("学习者已开通")
        assertions["learner_switched"] = await click_in_article("学习者", "切换")
        # Learning is a real Gate C3 workspace. The tutor boundary depends on
        # whether a real model and versioned source retrieval are configured.
        await wait_for("学习者能力状态")
        learned = await api(
            "/api/backend/api/user-center/library/want_to_learn/g4-heritage",
            "{method:'PUT',body:JSON.stringify({title:'G4 非遗学习样本',target_href:'/search'})}",
        )
        assertions["learning_asset_saved"] = learned["status"] == 200
        await command("Page.reload")
        await wait_for("今天从这里继续")
        body = await wait_for("G4 非遗学习样本")
        assertions["learner_boundary_visible"] = (
            "AI 非遗老师" in body
            and ("等待真实模型 API" in body or "版本化来源" in body)
        )
        learner = await api("/api/backend/api/identity/workbench?role=admin")
        assertions["persisted_context_authoritative"] = (
            learner["status"] == 200 and learner["body"].get("role") == "learner"
        )

        await click_when_ready("当前身份")
        await wait_for("管理与开通身份")
        await click_when_ready("管理与开通身份")
        await wait_for("切换与开通是两件事")
        assertions["buyer_switched"] = await click_in_article_when_ready("买家", "切换")
        body = await wait_for("买家能力状态")
        assertions["commerce_sandbox_boundary_visible"] = (
            "订单与履约" in body and "仅限内部沙盒订单与模拟履约" in body
        )
        await shot("multi-role-workbench.png")

        browser_errors = [
            item
            for item in events
            if item.get("method") == "Runtime.exceptionThrown"
            or (
                item.get("method") == "Log.entryAdded"
                and item.get("params", {}).get("entry", {}).get("level") == "error"
            )
        ]
        assertions["no_browser_exceptions"] = not browser_errors
        if not all(assertions.values()):
            raise RuntimeError(
                f"G4 assertions failed: { {key: value for key, value in assertions.items() if not value} }"
            )
        return {
            "status": "passed",
            "assertions": assertions,
            "browser_errors": len(browser_errors),
            "screenshots": screenshots,
        }


def main() -> None:
    if not PASSWORD:
        raise SystemExit("HAHA_G4_E2E_PASSWORD is required and is never stored in evidence")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    # Chromium can leave short-lived child processes writing profile files after the
    # parent exits on Linux CI. Profile cleanup must not turn passed assertions into
    # a failed acceptance job; the runner's ephemeral temp volume is discarded.
    with tempfile.TemporaryDirectory(
        prefix="haha-g4-workbench-e2e-", ignore_cleanup_errors=True
    ) as profile:
        process = subprocess.Popen(
            [
                str(find_chrome()),
                "--headless=new",
                f"--remote-debugging-port={DEBUG_PORT}",
                "--remote-allow-origins=*",
                f"--user-data-dir={profile}",
                "--disable-extensions",
                "--no-first-run",
                "--hide-scrollbars",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            endpoint = (
                f"http://127.0.0.1:{DEBUG_PORT}/json/new?"
                f"{urllib.parse.quote(WEB_URL, safe=':/?=&')}"
            )
            target = None
            for _ in range(100):
                try:
                    request = urllib.request.Request(endpoint, method="PUT")
                    with urllib.request.urlopen(request, timeout=2) as response:
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
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
