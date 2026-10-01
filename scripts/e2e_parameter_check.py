"""Exercise parameter editing and local generation in a real Chrome page."""

from __future__ import annotations

import asyncio
import base64
import json
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
SCREENSHOT = ARTIFACTS / "parameter-e2e-result.png"
REPORT = ARTIFACTS / "parameter-e2e-result.json"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
DEBUG_PORT = 9334
APP_URL = "http://localhost:8530/?space=script&new=1&model=local"


async def run(websocket_url: str) -> dict[str, object]:
    next_id = 0
    def stage(name: str, **details: object) -> None:
        REPORT.write_text(
            json.dumps({"stage": name, **details}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async with websockets.connect(websocket_url, max_size=20_000_000) as socket:
        async def command(method: str, params: dict[str, object] | None = None) -> dict:
            nonlocal next_id
            next_id += 1
            command_id = next_id
            await socket.send(json.dumps({"id": command_id, "method": method, "params": params or {}}))
            while True:
                message = json.loads(await asyncio.wait_for(socket.recv(), timeout=15))
                if message.get("id") == command_id:
                    if "error" in message:
                        raise RuntimeError(message["error"])
                    return message.get("result", {})

        async def evaluate(expression: str):
            result = await command(
                "Runtime.evaluate",
                {"expression": expression, "returnByValue": True, "awaitPromise": True},
            )
            return result.get("result", {}).get("value")

        async def wait_for(fragment: str, timeout: float = 30) -> str:
            deadline = time.monotonic() + timeout
            body = ""
            while time.monotonic() < deadline:
                body = str(await evaluate("document.body?.innerText || ''"))
                if fragment in body:
                    return body
                await asyncio.sleep(0.4)
            raise TimeoutError(f"Timed out waiting for {fragment}; body tail: {body[-1600:]}")

        async def select_option(label_text: str, option_text: str, arrow_steps: int) -> None:
            scrolled = await evaluate(
                "((labelText) => {"
                "const label=[...document.querySelectorAll('label')].find(x=>x.innerText.trim()===labelText);"
                "const control=label?.closest('[data-testid=stSelectbox]')?.querySelector('[role=combobox]');"
                "if(!control)return false; control.scrollIntoView({block:'center'}); return true;"
                f"}})({json.dumps(label_text, ensure_ascii=False)})"
            )
            if not scrolled:
                raise RuntimeError(f"未找到参数下拉框：{label_text}")
            await asyncio.sleep(0.3)
            control_rect = await evaluate(
                "((labelText) => {"
                "const labels=[...document.querySelectorAll('label')];"
                "const label=labels.find(x=>x.innerText.trim()===labelText);"
                "const box=label?.closest('[data-testid=stSelectbox]');"
                "const control=box?.querySelector('[role=combobox]');"
                "if(!control)return null; const r=control.getBoundingClientRect();"
                "return {x:r.left+r.width/2,y:r.top+r.height/2};"
                f"}})({json.dumps(label_text, ensure_ascii=False)})"
            )
            if not control_rect:
                raise RuntimeError(f"未找到参数下拉框：{label_text}")
            await command("Input.dispatchMouseEvent", {"type": "mousePressed", "x": control_rect["x"], "y": control_rect["y"], "button": "left", "clickCount": 1})
            await command("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": control_rect["x"], "y": control_rect["y"], "button": "left", "clickCount": 1})
            await asyncio.sleep(0.25)
            option_rect = await evaluate(
                "((optionText) => {"
                "const nodes=[...document.querySelectorAll('body *')].filter(x=>x.textContent.trim()===optionText);"
                "const option=nodes.filter(x=>{const r=x.getBoundingClientRect();return r.width>0&&r.height>0;}).sort((a,b)=>a.children.length-b.children.length)[0];"
                "if(!option)return null; const r=option.getBoundingClientRect();"
                "return {x:r.left+r.width/2,y:r.top+r.height/2};"
                f"}})({json.dumps(option_text, ensure_ascii=False)})"
            )
            if option_rect:
                await command("Input.dispatchMouseEvent", {"type": "mousePressed", "x": option_rect["x"], "y": option_rect["y"], "button": "left", "clickCount": 1})
                await command("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": option_rect["x"], "y": option_rect["y"], "button": "left", "clickCount": 1})
                await asyncio.sleep(0.25)
                return
            key = "ArrowDown" if arrow_steps >= 0 else "ArrowUp"
            for _ in range(abs(arrow_steps)):
                await command("Input.dispatchKeyEvent", {"type": "keyDown", "key": key})
                await command("Input.dispatchKeyEvent", {"type": "keyUp", "key": key})
            await command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter"})
            await command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter"})
            await asyncio.sleep(0.25)

        await command("Runtime.enable")
        await command("Page.enable")
        await command("Page.navigate", {"url": APP_URL})
        stage("navigated")
        await wait_for("应用参数并生成创作判断")
        stage("workspace-ready")
        await wait_for("本地演示 · 未调用模型 API", 15)
        stage("local-model-ready")
        await select_option("发布平台", "抖音", -1)
        await select_option("时长", "30秒", -1)
        await select_option("画幅", "3:4", 3)
        await select_option("表达气质", "诗意东方", 4)
        await evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(0.3)
        focused = await evaluate(
            "(() => { const el=[...document.querySelectorAll('textarea')].find(x=>x.placeholder?.includes('按右侧当前参数生成'));"
            "if(!el)return false; el.focus(); return true; })()"
        )
        if not focused:
            raise RuntimeError("底部创作对话框不存在")
        await command("Input.insertText", {"text": "中国剪纸"})
        await command(
            "Input.dispatchKeyEvent",
            {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13},
        )
        await command(
            "Input.dispatchKeyEvent",
            {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13},
        )
        await asyncio.sleep(0.6)
        stage("chat-generation-submitted")
        await asyncio.sleep(5)
        body = str(await evaluate("document.body?.innerText || ''"))
        stage("post-click", body_tail=body[-2500:])
        if "本次创作判断" not in body:
            raise RuntimeError(f"生成后未出现结果。页面末尾：{body[-1200:]}")
        chat_path_checks = {
            "platform": "推荐平台\n抖音" in body,
            "spec": "推荐规格\n30秒 · 3:4" in body,
            "tone": "表达气质\n诗意东方" in body,
        }
        if not all(chat_path_checks.values()):
            raise RuntimeError(f"底部对话生成绕过了右侧参数：{chat_path_checks}")
        apply_state = await evaluate(
            "(() => { const button=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('应用参数并重新生成'));"
            "return button ? {found:true, disabled:button.disabled, ariaDisabled:button.getAttribute('aria-disabled')} : {found:false}; })()"
        )
        if not apply_state or not apply_state.get("found"):
            raise RuntimeError("已有结果后未找到‘应用参数并重新生成’按钮")
        if apply_state.get("disabled"):
            raise RuntimeError(f"重新生成按钮被禁用：{apply_state}")
        await select_option("发布平台", "B站", 2)
        await select_option("时长", "30秒", 0)
        await select_option("画幅", "16:9", -2)
        await select_option("表达气质", "人物纪实", -1)
        await evaluate(
            "(() => { const button=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('应用参数并重新生成'));"
            "button.click(); return true; })()"
        )
        stage("regenerate-clicked", apply_state=apply_state)
        await wait_for("已应用参数并重新生成：B站 · 30秒 · 16:9 · 人物纪实", 30)
        body = str(await evaluate("document.body?.innerText || ''"))
        result_checks = {
            "summary_platform": "平台 B站" in body,
            "result_platform": "推荐平台\nB站" in body,
            "result_spec": "推荐规格\n30秒 · 16:9" in body,
            "result_tone": "表达气质\n人物纪实" in body,
        }
        if not all(result_checks.values()):
            raise RuntimeError(f"结果区没有完整应用参数：{result_checks}; body tail: {body[-2200:]}")
        stage("regenerate-complete", body_tail=body[-2500:])
        confirmed = await evaluate(
            "(() => { const button=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('确认并生成完整脚本'));"
            "if(!button)return false; button.click(); return true; })()"
        )
        if not confirmed:
            raise RuntimeError("未找到‘确认并生成完整脚本’按钮")
        body = await wait_for("26–30秒", 20)
        result_checks["timeline"] = "26–30秒" in body and "38–45 秒" not in body
        result_checks["tone_content"] = bool(
            await evaluate(
                "[...document.querySelectorAll('textarea')].some(x=>x.value.includes('双手、停顿和反复尝试'))"
            )
        )
        if not result_checks["timeline"] or not result_checks["tone_content"]:
            raise RuntimeError(f"完整脚本未应用时长或气质：{result_checks}")
        await evaluate(
            "(() => { const node=[...document.querySelectorAll('body *')].find(x=>x.textContent.trim()==='本次创作判断');"
            "node?.scrollIntoView({block:'start'}); return !!node; })()"
        )
        await asyncio.sleep(0.4)
        shot = await command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
        SCREENSHOT.write_bytes(base64.b64decode(shot["data"]))
        return {
            "has_result": "本次创作判断" in body,
            "has_type_error": "unexpected keyword argument 'asset_context'" in body,
            "has_local_mode": "本地演示" in body,
            "regeneration_confirmed": "已应用参数并重新生成：B站 · 30秒 · 16:9 · 人物纪实" in body,
            "apply_button_state": apply_state,
            "result_checks": result_checks,
            "chat_path_checks": chat_path_checks,
            "screenshot": str(SCREENSHOT),
        }


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps({"stage": "starting"}), encoding="utf-8")
    profile = ARTIFACTS / f"parameter-e2e-profile-{time.time_ns()}"
    profile.mkdir(exist_ok=True)
    process = subprocess.Popen(
        [
            str(CHROME),
            "--headless=new",
            f"--remote-debugging-port={DEBUG_PORT}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            "--disable-extensions",
            "--disable-translate",
            "--no-first-run",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        endpoint = f"http://127.0.0.1:{DEBUG_PORT}/json/new?{urllib.parse.quote(APP_URL, safe=':/?=&')}"
        target = None
        for _ in range(80):
            try:
                request = urllib.request.Request(endpoint, method="PUT")
                with urllib.request.urlopen(request, timeout=2) as response:
                    target = json.load(response)
                break
            except Exception:
                time.sleep(0.25)
        if target is None:
            raise RuntimeError("Chrome DevTools endpoint did not start")
        REPORT.write_text(json.dumps({"stage": "connected"}), encoding="utf-8")
        result = asyncio.run(asyncio.wait_for(run(target["webSocketDebuggerUrl"]), timeout=75))
        REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False), flush=True)
    except Exception as exc:
        REPORT.write_text(
            json.dumps({"stage": "failed", "error": repr(exc)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raise
    finally:
        process.terminate()
        process.wait(timeout=5)


if __name__ == "__main__":
    main()
