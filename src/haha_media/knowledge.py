"""Two isolated, traceable knowledge bases for the creator workspace MVP."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

SOURCE_NAME = "HAHA飞颐项目营销端总材料包(1).docx"


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    id: str
    knowledge_base: str
    title: str
    content: str
    tags: tuple[str, ...]
    metadata: tuple[tuple[str, str], ...]
    status: str = "active"
    version: str = "1.0"
    source_name: str = SOURCE_NAME


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    chunk: KnowledgeChunk
    score: float


@dataclass(frozen=True, slots=True)
class RetrievalTrace:
    generation_id: str
    user_query: str
    creative_query: str
    operation_query: str
    creative_chunks_used: tuple[str, ...]
    operation_chunks_used: tuple[str, ...]
    rerank_scores: tuple[tuple[str, float], ...]
    document_version: str
    model: str
    created_at: str


CREATIVE_METHOD_CHUNKS = (
    KnowledgeChunk("M-001", "creative_method", "平台化结构化剧本", "先将一句话或大纲扩写，再按集数、场次拆分。每场明确场景、人物动作、情绪与精简台词，结尾保留可继续追问的悬念。", ("剧本结构", "人物", "台词", "分场"), (("method_type", "剧本结构"), ("stability", "stable"))),
    KnowledgeChunk("M-002", "creative_method", "工艺过程结构化分镜", "逐场拆为远景、中景、近景与特写，明确镜头运动、人物动作、机位、构图、台词和时长。工艺内容优先用手部与材料细节建立视觉信息。", ("镜头设计", "分镜", "非遗工艺", "手部"), (("method_type", "分镜"), ("stability", "stable"))),
    KnowledgeChunk("M-003", "creative_method", "人物与资产一致性", "角色、产品、场景和道具应建立统一参考资产并跨镜头复用。人物参考至少覆盖正面与侧面；生成后校验人物、场景与产品细节，不一致时回到对应节点重制。", ("人物一致性", "Asset Lock", "资产复用"), (("method_type", "资产一致性"), ("stability", "stable"))),
    KnowledgeChunk("M-004", "creative_method", "首帧与视频镜头生成", "根据结构化分镜和已锁定资产生成每个镜头参考首帧，再基于首帧、动作和运镜提示生成单镜头视频。每段明确动作幅度、镜头运动和目标时长。", ("首帧", "视频生成", "运镜"), (("method_type", "视频生成"), ("stability", "stable"))),
    KnowledgeChunk("M-005", "creative_method", "视听剪辑与连贯性检查", "按分镜顺序拼接镜头，补充字幕、调色、转场、配音、音效和背景音乐。节奏点应服务动作和叙事；成片检查画面连贯、人物产品一致、字幕错字与音频杂音。", ("剪辑", "节奏", "一致性", "审片"), (("method_type", "视频生成"), ("stability", "stable"))),
)


OPERATION_STRATEGY_CHUNKS = (
    KnowledgeChunk("O-001", "operation_strategy", "平台选择与平台化改写", "先确定抖音、小红书、B站、视频号或 TikTok，再按平台调性调整叙事密度、画幅、时长与表达。平台建议不是文化事实，也不是绝对规律。", ("平台", "改写", "时长", "画幅"), (("strategy_type", "structure"), ("confidence", "high"))),
    KnowledgeChunk("O-002", "operation_strategy", "前三秒强 Hook", "开篇直接呈现最有变化的动作、材料细节或反差问题，避免先讲大段背景。Hook 与正文必须兑现同一件事，不能靠夸张历史结论制造吸引力。", ("Hook", "前三秒", "文化科普"), (("strategy_type", "hook"), ("confidence", "high"))),
    KnowledgeChunk("O-003", "operation_strategy", "标题封面与投放素材", "从成片中提炼多组标题、封面文字、简介、标签和钩子切片，形成 A/B 测试包。标题突出具体动作或观众收益，避免使用未经核验的年代、级别和身份。", ("标题", "封面", "A/B测试", "投放素材"), (("strategy_type", "title"), ("confidence", "high"))),
    KnowledgeChunk("O-004", "operation_strategy", "互动与结尾设计", "结尾用一个具体、低门槛的问题承接评论或收藏，例如询问观众想继续看哪一步。系列内容可在结尾留下下一期可兑现的悬念。", ("互动", "结尾", "收藏", "评论"), (("strategy_type", "interaction"), ("confidence", "medium"))),
    KnowledgeChunk("O-005", "operation_strategy", "数据复盘闭环", "发布后关注 CTR、完播率、关键节点留存与 ROI，定位表现较弱的标题、开头或镜头，再把结论反馈到下一批剧本和分镜。指标用于复盘，不用于承诺播放量或涨粉。", ("CTR", "完播率", "留存", "ROI", "复盘"), (("strategy_type", "data_analysis"), ("confidence", "high"))),
)


def _tokens(text: str) -> Counter[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    latin = re.findall(r"[a-z0-9]+", normalized)
    chinese = re.findall(r"[\u4e00-\u9fff]", normalized)
    bigrams = ["".join(chinese[i : i + 2]) for i in range(max(0, len(chinese) - 1))]
    return Counter(latin + chinese + bigrams)


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    shared = set(left) & set(right)
    dot = sum(left[token] * right[token] for token in shared)
    norm_left = math.sqrt(sum(value * value for value in left.values()))
    norm_right = math.sqrt(sum(value * value for value in right.values()))
    return dot / (norm_left * norm_right) if norm_left and norm_right else 0.0


def _hybrid_search(query: str, chunks: tuple[KnowledgeChunk, ...], limit: int) -> tuple[RetrievalHit, ...]:
    query_tokens = _tokens(query)
    query_terms = set(query_tokens)
    hits: list[RetrievalHit] = []
    for chunk in chunks:
        if chunk.status != "active" or dict(chunk.metadata).get("stability") == "deprecated":
            continue
        text = " ".join((chunk.title, chunk.content, *chunk.tags))
        chunk_tokens = _tokens(text)
        keyword = len(query_terms & set(chunk_tokens)) / max(1, len(query_terms))
        semantic = _cosine(query_tokens, chunk_tokens)
        tag_bonus = 0.08 * sum(tag.lower() in query.lower() for tag in chunk.tags)
        score = min(1.0, keyword * 0.45 + semantic * 0.45 + tag_bonus)
        hits.append(RetrievalHit(chunk, round(score, 3)))
    hits.sort(key=lambda hit: (hit.score, hit.chunk.id), reverse=True)
    return tuple(hits[:limit])


def retrieve_creative_methods(query: str, limit: int = 5) -> tuple[RetrievalHit, ...]:
    """Hybrid retrieval over the isolated creative-method knowledge base."""
    return _hybrid_search(query, CREATIVE_METHOD_CHUNKS, limit)


def retrieve_operation_strategies(query: str, limit: int = 5) -> tuple[RetrievalHit, ...]:
    """Hybrid retrieval over the isolated operation-strategy knowledge base."""
    return _hybrid_search(query, OPERATION_STRATEGY_CHUNKS, limit)


def build_retrieval_trace(
    user_query: str,
    creative_query: str,
    operation_query: str,
    creative_hits: tuple[RetrievalHit, ...],
    operation_hits: tuple[RetrievalHit, ...],
) -> RetrievalTrace:
    hits = creative_hits + operation_hits
    return RetrievalTrace(
        generation_id=str(uuid4()),
        user_query=user_query,
        creative_query=creative_query,
        operation_query=operation_query,
        creative_chunks_used=tuple(hit.chunk.id for hit in creative_hits),
        operation_chunks_used=tuple(hit.chunk.id for hit in operation_hits),
        rerank_scores=tuple((hit.chunk.id, hit.score) for hit in hits),
        document_version="1.0",
        model="deterministic-provider",
        created_at=datetime.now(UTC).isoformat(),
    )
