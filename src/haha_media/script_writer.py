"""Deterministic short-form content script generator for the media MVP."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace

from haha_media.knowledge import (
    CREATIVE_METHOD_CHUNKS,
    OPERATION_STRATEGY_CHUNKS,
    RetrievalTrace,
    build_retrieval_trace,
    retrieve_creative_methods,
    retrieve_operation_strategies,
)
from haha_media.model_router import CallEvidence, ModelRouter, get_model_router


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
    method_sources: tuple[tuple[str, str], ...] = ()
    strategy_sources: tuple[tuple[str, str], ...] = ()
    fact_checks: tuple[str, ...] = ()
    retrieval_trace: RetrievalTrace | None = None
    model_evidence: CallEvidence | None = None


def generate_content_script(brief: ContentBrief) -> ContentScript:
    """Generate an editable, claim-cautious 45-second production package."""
    craft = brief.craft.strip()
    story_seed = brief.story_seed.strip()
    if not craft:
        raise ValueError("请先填写要讲述的技艺或作品名称。")
    context = story_seed or "一位手艺人与一件正在完成的作品"
    user_query = " ".join(
        (craft, context, brief.goal, brief.audience, brief.platform, brief.duration, brief.aspect_ratio, brief.tone)
    )
    creative_query = " ".join(
        (craft, "传统工艺短视频", context, brief.duration, brief.tone, "手部动作 镜头 结构化分镜 人物一致性")
    )
    operation_query = " ".join(
        (brief.platform, brief.goal, brief.audience, brief.duration, brief.aspect_ratio, "前三秒 Hook 标题 封面 互动")
    )
    creative_hits = retrieve_creative_methods(creative_query, limit=5)
    operation_hits = retrieve_operation_strategies(operation_query, limit=5)
    trace = build_retrieval_trace(
        user_query, creative_query, operation_query, creative_hits, operation_hits
    )
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
    method_summary = "、".join(hit.chunk.title for hit in creative_hits[:3])
    strategy_summary = "、".join(hit.chunk.title for hit in operation_hits[:3])
    judgment = (
        ("创作主体", craft),
        ("内容类型", brief.goal),
        ("目标受众", brief.audience),
        ("推荐平台", brief.platform),
        ("推荐规格", f"{brief.duration} · {brief.aspect_ratio}"),
        ("内容结构", structure),
        ("创作方法", method_summary),
        ("运营策略", strategy_summary),
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
    sources = ("当前未接入非遗事实库", "创作者现场资料 · 待补充并核验")
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
    method_sources = tuple((hit.chunk.id, hit.chunk.title) for hit in creative_hits)
    strategy_sources = tuple((hit.chunk.id, hit.chunk.title) for hit in operation_hits)
    fact_checks = (
        f"{craft} 的起源年代、地域归属与非遗级别",
        "具体人物身份、传承关系及代表性称号",
        "材料、工序与纹样含义等客观工艺陈述",
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
        method_sources,
        strategy_sources,
        fact_checks,
        trace,
    )


def generate_content_script_with_model(
    brief: ContentBrief, router: ModelRouter | None = None
) -> ContentScript:
    """Generate through the configured model while preserving KB and audit evidence."""
    base = generate_content_script(brief)
    active_router = router or get_model_router()
    if not active_router.status().text_ready:
        raise ValueError("尚未配置可用的 DeepSeek API。")
    method_lookup = {chunk.id: chunk for chunk in CREATIVE_METHOD_CHUNKS}
    strategy_lookup = {chunk.id: chunk for chunk in OPERATION_STRATEGY_CHUNKS}
    method_context = "\n\n".join(
        f"[{chunk_id}] {method_lookup[chunk_id].title}\n{method_lookup[chunk_id].content}"
        for chunk_id, _ in base.method_sources
        if chunk_id in method_lookup
    )
    strategy_context = "\n\n".join(
        f"[{chunk_id}] {strategy_lookup[chunk_id].title}\n{strategy_lookup[chunk_id].content}"
        for chunk_id, _ in base.strategy_sources
        if chunk_id in strategy_lookup
    )
    system_prompt = """你是 HAHA AI 图文脚本创作系统。你会收到两个严格分区的知识上下文。
CREATIVE_METHOD_CONTEXT 只回答怎么创作；OPERATION_STRATEGY_CONTEXT 只回答怎么适配平台和受众。
它们都不是非遗事实来源。不得自行确认历史、地域、人物身份、非遗级别或起源年代；相关陈述必须标记待事实核验。
请只输出合法 JSON，不要输出 Markdown。JSON 必须包含 title、hook、voiceover、shots、caption、tags 六个字段。
voiceover 和 shots 必须是字符串数组，tags 也是字符串数组。"""
    user_prompt = f"""创作设定：
{json.dumps({"主题": brief.craft, "瞬间": brief.story_seed, "受众": brief.audience, "平台": brief.platform, "气质": brief.tone, "目标": brief.goal, "时长": brief.duration, "画幅": brief.aspect_ratio}, ensure_ascii=False)}

<CREATIVE_METHOD_CONTEXT>
{method_context}
</CREATIVE_METHOD_CONTEXT>

<OPERATION_STRATEGY_CONTEXT>
{strategy_context}
</OPERATION_STRATEGY_CONTEXT>

生成一份可拍摄的短内容方案。不要添加上下文没有提供的文化事实。"""
    result = active_router.generate_json(
        "creation_judgement",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.35,
        max_tokens=4096,
    )
    data = result.data

    def text_value(key: str, fallback: str) -> str:
        value = data.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else fallback

    def tuple_value(key: str, fallback: tuple[str, ...], minimum: int = 1) -> tuple[str, ...]:
        value = data.get(key)
        if not isinstance(value, list):
            return fallback
        items = tuple(str(item).strip() for item in value if str(item).strip())
        return items if len(items) >= minimum else fallback

    return replace(
        base,
        title=text_value("title", base.title),
        hook=text_value("hook", base.hook),
        voiceover=tuple_value("voiceover", base.voiceover, 3),
        shots=tuple_value("shots", base.shots, 3),
        caption=text_value("caption", base.caption),
        tags=tuple_value("tags", base.tags, 2),
        model_evidence=result.evidence,
    )
