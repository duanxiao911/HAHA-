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
    goal: str = "文化科普"
    duration: str = "45秒"
    aspect_ratio: str = "9:16"
    content_count: str = "单条内容"
    fact_level: str = "平衡"
    model_tier: str = "标准"


@dataclass(frozen=True, slots=True)
class ContentScript:
    title: str
    hook: str
    voiceover: tuple[str, ...]
    shots: tuple[str, ...]
    caption: str
    tags: tuple[str, ...]
    judgment: tuple[tuple[str, str], ...] = ()
    storyboard: tuple[tuple[str, ...], ...] = ()
    titles: tuple[str, ...] = ()
    covers: tuple[str, ...] = ()
    interactions: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    audits: tuple[tuple[str, str], ...] = ()
    operation_scores: tuple[tuple[str, str], ...] = ()


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
    tags = ("#非遗", f"#{craft}", "#传统技艺", "#手艺人的一天")
    structure = "视觉钩子 → 工艺过程 → 人物细节 → 文化知识 → 情绪收尾"
    judgment = (
        ("创作主体", craft),
        ("内容类型", brief.goal),
        ("目标受众", brief.audience),
        ("推荐平台", brief.platform),
        ("推荐规格", f"{brief.duration} · {brief.aspect_ratio}"),
        ("内容结构", structure),
        ("核心卖点", f"“{context}”具备清晰动作和材料变化，适合作为视觉记忆点。"),
        ("事实风险", "当前演示资料不足以确认具体起源年代与代表人物，不建议自行补写。"),
    )
    storyboard = (
        (
            "01",
            "0–3秒",
            "工艺现场",
            "近景",
            "缓慢推近",
            context,
            "专注",
            hook,
            "环境声",
            "实拍",
            "待补充",
        ),
        (
            "02",
            "3–12秒",
            "工作台",
            "特写",
            "固定镜头",
            "材料与双手完成关键动作",
            "稳定",
            voiceover[1],
            "材料声",
            "实拍",
            "创作者确认",
        ),
        (
            "03",
            "12–28秒",
            "工坊",
            "中近景",
            "横移",
            "人物状态与作品细节交替",
            "投入",
            voiceover[2],
            "轻音乐",
            "实拍",
            "项目方资料",
        ),
        (
            "04",
            "28–40秒",
            "展示区",
            "近景",
            "慢推",
            "成品或半成品呈现纹理",
            "平静",
            "过程留下的痕迹，就是作品的一部分。",
            "轻音乐",
            "实拍",
            "创作者确认",
        ),
        (
            "05",
            "40–45秒",
            "作品前",
            "特写",
            "静止",
            "停留在一个可继续追问的细节",
            "好奇",
            "你还想了解哪一步？",
            "环境声",
            "实拍",
            "—",
        ),
    )
    titles = (
        f"{craft}最动人的，可能就是这一瞬间",
        f"45秒，看见{craft}如何慢慢成形",
        f"别急着划走：{craft}的细节会说话",
    )
    covers = (f"{craft}成形的一刻", "手艺不会说话，细节会", "这一瞬间值得被看见")
    interactions = ("你最想继续看哪一道工序？", "下一次想认识哪一门手艺？")
    sources = (
        "HAHA 非遗事实库 · 项目基础条目（演示）",
        "创作者现场资料 · 待补充",
        "平台运营策略库 · 规则模板",
    )
    audits = (
        ("通过", "项目名称在全文保持一致"),
        ("需确认", "地域、非遗级别与代表人物尚未提供权威来源"),
        ("风险", "禁止加入未经来源支持的明确起源年份"),
        ("通过", "镜头与情绪表达已与事实陈述分离"),
    )
    operation_scores = (
        ("平台适配度", "高"),
        ("前3秒吸引力", "高"),
        ("收藏价值", "中"),
        ("评论潜力", "中"),
        ("知识价值", "中"),
    )
    return ContentScript(
        title,
        hook,
        voiceover,
        shots,
        caption,
        tags,
        judgment,
        storyboard,
        titles,
        covers,
        interactions,
        sources,
        audits,
        operation_scores,
    )
