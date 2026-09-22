"""Deterministic short-form content script generator for the media MVP."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContentBrief:
    craft: str
    story_seed: str
    audience: str
    platform: str
    tone: str


@dataclass(frozen=True, slots=True)
class ContentScript:
    title: str
    hook: str
    voiceover: tuple[str, ...]
    shots: tuple[str, ...]
    caption: str
    tags: tuple[str, ...]


def generate_content_script(brief: ContentBrief) -> ContentScript:
    """Generate an editable, claim-cautious 45-second production package."""
    craft = brief.craft.strip()
    story_seed = brief.story_seed.strip()
    if not craft:
        raise ValueError("请先填写要讲述的技艺或作品名称。")
    context = story_seed or "一位手艺人与一件正在完成的作品"
    title = f"{craft}：把时间留在手上"
    hook = f"你见过 {craft} 的这一刻吗？先别急着划走。"
    voiceover = (
        hook,
        f"今天从 {context} 开始，我们只看一个细节。",
        f"它不急着给出结论，而是让 {craft} 的过程自己说话。",
        "如果你也想继续了解它的材料、纹样或来处，留言问 HAHA。",
    )
    shots = (
        "0–3 秒｜手部或材料近景；镜头静止，保留环境声。",
        "3–12 秒｜展示一个关键动作；用局部画面而不是完整讲解。",
        "12–28 秒｜手艺人工作状态与作品细节交替；字幕只陈述已确认的事实。",
        "28–40 秒｜成品或半成品慢推；留下一个可被继续追问的细节。",
        "40–45 秒｜片尾提问：你还想了解哪一步？",
    )
    caption = (
        f"{craft} 的故事，从一个细节开始。\n\n"
        f"这次我们记录的是：{context}。\n"
        "文中涉及历史、地域或传承信息，请在发布前补充可核验来源。"
    )
    tags = ("#非遗", f"#{craft}", "#手艺人的一天", "#文化故事")
    return ContentScript(title, hook, voiceover, shots, caption, tags)
