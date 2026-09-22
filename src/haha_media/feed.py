"""Original placeholder stories for the clean-slate media prototype."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Story:
    slug: str
    title: str
    category: str
    duration: str
    summary: str
    ai_answer: str
    cover_markup: str
    author: str = "HAHA 文化记录者"
    region: str = "中国"
    views: str = "1.2万"
    interactions: str = "326"


def _cover(emoji: str, tone: str, label: str) -> str:
    return f'<div class="cover {tone}"><span>{emoji}</span><small>{label}</small></div>'


STORIES = (
    Story(
        "one-thread",
        "一根线，怎样绣出远方？",
        "刺绣 · 人物故事",
        "02:18",
        "从一双手的重复练习开始，看看图案如何成为记忆的语言。",
        "刺绣不仅是装饰。它把色彩、纹样与个人经验缝在一起；接下来可以从纹样、工序或地域故事继续问起。",
        _cover("〰", "red", "EP. 01 · HANDS & MEMORY"),
        author="阿锦的绣房",
        region="贵州",
        views="8.6万",
        interactions="1,204",
    ),
    Story(
        "sound-of-clay",
        "泥土被火记住的声音",
        "陶艺 · 工序观察",
        "01:32",
        "拉坯、晾晒、入窑：每一步都在和时间协商。",
        "器物的形状来自手的控制，也来自材料和火候。你可以继续问：为什么同一种釉色会有不同变化？",
        _cover("◒", "green", "PROCESS NOTE"),
        author="泥与火工作室",
        region="江西景德镇",
        views="5.4万",
        interactions="836",
    ),
    Story(
        "pattern-walks",
        "一朵纹样，走过多少地方？",
        "纹样 · 文化观察",
        "00:54",
        "把一个常见图案拆开看，它会连接祝愿、自然与日常生活。",
        "理解纹样时，先看它出现在哪里、和什么材料相遇；不要把不同地区、时代的含义混成一句结论。",
        _cover("✣", "blue", "PATTERN FIELD"),
        author="纹样观察所",
        region="云南",
        views="3.1万",
        interactions="527",
    ),
    Story(
        "quiet-workshop",
        "工作台上的安静时刻",
        "手艺人 · 日常",
        "01:07",
        "镜头不急着解释，只记录一件作品慢慢成形。",
        "非遗的魅力常常藏在重复和耐心里。媒体页先让人停下来，再决定要不要继续了解。",
        _cover("⌁", "gold", "WORKSHOP DIARY"),
        author="青年手艺档案",
        region="浙江",
        views="2.8万",
        interactions="419",
    ),
    Story(
        "gift-language",
        "礼物为什么需要一个故事？",
        "礼物 · 文化连接",
        "00:48",
        "比价格更早被记住的，往往是你送出它时说的那句话。",
        "礼物推荐不应只看标签。它应连接送礼对象、场景、观看过的内容和你真正想表达的心意。",
        _cover("◇", "purple", "GIFT LANGUAGE"),
        author="HAHA 礼物研究室",
        region="福建",
        views="1.9万",
        interactions="288",
    ),
)
