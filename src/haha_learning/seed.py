"""Versioned C3 catalog containing platform-literacy material only.

The seed deliberately avoids asserting formal intangible-cultural-heritage facts. It teaches
how to preserve source and trust metadata while the authoritative knowledge integration is
still unavailable.
"""

from __future__ import annotations

import json

from haha_learning.domain import (
    AchievementDefinition,
    KnowledgeSource,
    LearningPath,
    LearningUnit,
    Quiz,
    QuizQuestion,
)

CATALOG_VERSION = 1
CREATED_AT = "2026-10-16T00:00:00.000Z"
SOURCE_ID = "learning-source-c3-demo"
PATH_ID = "learning-path-source-literacy"
LESSON_UNIT_ID = "learning-unit-source-check"
QUIZ_UNIT_ID = "learning-unit-source-quiz"
QUIZ_ID = "learning-quiz-source-literacy"


def catalog_records(workspace_id: str) -> dict[str, list[object]]:
    source = KnowledgeSource(
        id=SOURCE_ID,
        workspace_id=workspace_id,
        title="HAHA Gate C3 内部学习说明",
        publisher="HAHA 内部演示目录",
        source_type="internal_demo",
        url="",
        version=CATALOG_VERSION,
        verification_status="demo_only",
        provenance="system_seed",
        checked_at=CREATED_AT,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )
    path = LearningPath(
        id=PATH_ID,
        workspace_id=workspace_id,
        title="从来源开始：可信学习入门",
        summary="学习区分来源、版本和可信状态；本路径不提供正式非遗事实认定。",
        status="published",
        version=CATALOG_VERSION,
        provenance="system_seed",
        verification_status="demo_only",
        source_note="内部功能验证课程；不是权威非遗名录、认证或教学结论。",
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )
    units = [
        LearningUnit(
            id=LESSON_UNIT_ID,
            path_id=PATH_ID,
            workspace_id=workspace_id,
            position=1,
            kind="lesson",
            title="读懂来源与可信状态",
            summary="完成前先确认主题、来源、版本与可信状态，并保留无法确认的边界。",
            source_id=SOURCE_ID,
            version=CATALOG_VERSION,
            required=True,
            estimated_minutes=5,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        ),
        LearningUnit(
            id=QUIZ_UNIT_ID,
            path_id=PATH_ID,
            workspace_id=workspace_id,
            position=2,
            kind="quiz",
            title="来源与可信状态测验",
            summary="由服务端判定结果，并保存不可变答题快照。",
            source_id=SOURCE_ID,
            version=CATALOG_VERSION,
            required=True,
            estimated_minutes=3,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        ),
    ]
    quiz = Quiz(
        id=QUIZ_ID,
        workspace_id=workspace_id,
        path_id=PATH_ID,
        unit_id=QUIZ_UNIT_ID,
        title="来源与可信状态测验",
        version=CATALOG_VERSION,
        pass_score=67,
        status="published",
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )
    questions = [
        QuizQuestion(
            id="learning-question-trust",
            quiz_id=QUIZ_ID,
            workspace_id=workspace_id,
            position=1,
            prompt="资料标记为“待核验”时，最合适的处理是什么？",
            choices_json=json.dumps(
                ["直接作为权威事实发布", "保留来源并明确尚未确认", "删除所有来源信息"],
                ensure_ascii=False,
            ),
            correct_choice=1,
            explanation="待核验资料不能被提升为已确认事实。",
            source_id=SOURCE_ID,
            version=CATALOG_VERSION,
        ),
        QuizQuestion(
            id="learning-question-card",
            quiz_id=QUIZ_ID,
            workspace_id=workspace_id,
            position=2,
            prompt="一张可追溯知识卡至少应保留什么？",
            choices_json=json.dumps(
                ["只有标题", "主题、来源、版本和可信状态", "只有模型回答"],
                ensure_ascii=False,
            ),
            correct_choice=1,
            explanation="知识卡必须能回到具体来源与版本，并显示可信状态。",
            source_id=SOURCE_ID,
            version=CATALOG_VERSION,
        ),
        QuizQuestion(
            id="learning-question-ai",
            quiz_id=QUIZ_ID,
            workspace_id=workspace_id,
            position=3,
            prompt="没有真实模型与可信知识检索接口时，AI 非遗老师应处于什么状态？",
            choices_json=json.dumps(
                ["用模板回答冒充接通", "明确标记为 BLOCKED", "随机生成来源"],
                ensure_ascii=False,
            ),
            correct_choice=1,
            explanation="未接通真实能力时必须明确阻断，不能用 Mock 冒充。",
            source_id=SOURCE_ID,
            version=CATALOG_VERSION,
        ),
    ]
    achievements = [
        AchievementDefinition(
            id="achievement-first-unit",
            workspace_id=workspace_id,
            code="first_unit",
            title="第一步",
            description="完成第一个真实学习节点。",
            event_type="unit.completed",
            threshold=1,
            points=10,
            version=1,
            status="active",
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        ),
        AchievementDefinition(
            id="achievement-first-card",
            workspace_id=workspace_id,
            code="first_card",
            title="有据可查",
            description="保存第一张带来源与可信状态的知识卡。",
            event_type="knowledge_card.saved",
            threshold=1,
            points=10,
            version=1,
            status="active",
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        ),
        AchievementDefinition(
            id="achievement-first-quiz",
            workspace_id=workspace_id,
            code="first_quiz_pass",
            title="检验理解",
            description="第一次通过服务端判定的测验。",
            event_type="quiz.passed",
            threshold=1,
            points=20,
            version=1,
            status="active",
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        ),
    ]
    return {
        "sources": [source],
        "paths": [path],
        "units": units,
        "quizzes": [quiz],
        "questions": questions,
        "achievements": achievements,
    }
