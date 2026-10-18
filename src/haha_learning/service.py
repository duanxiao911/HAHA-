"""Application service for durable learning, quizzes, tasks, streaks, and achievements."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from haha_learning.domain import (
    EnrollmentStatus,
    KnowledgeCard,
    LearningActivityCommit,
    LearningConflictError,
    LearningEvent,
    LearningNotFoundError,
    LearningPermissionError,
    LearningProgress,
    LearningTutorRateLimitError,
    LearningTutorUnavailableError,
    PathEnrollment,
    ProgressStatus,
    QuizAttempt,
    TutorInteraction,
)
from haha_learning.repository import LearningRepository
from haha_learning.tutor import HeritageTutor
from haha_media.model_router import ModelCallError
from haha_user_center.domain import LibraryKind

COUNTED_EVENT_TYPES = frozenset(
    {"unit.completed", "knowledge_card.saved", "quiz.passed"}
)


def _now_dt() -> datetime:
    return datetime.now(UTC)


def _timestamp(value: datetime | None = None) -> str:
    return (value or _now_dt()).isoformat(timespec="milliseconds")


def _stable_id(prefix: str, *values: str) -> str:
    digest = hashlib.sha256(":".join(values).encode()).hexdigest()[:32]
    return f"{prefix}_{digest}"


def _clean(value: str, *, label: str, maximum: int, required: bool = False) -> str:
    cleaned = value.strip()
    if required and not cleaned:
        raise ValueError(f"{label}不能为空")
    if len(cleaned) > maximum:
        raise ValueError(f"{label}不能超过 {maximum} 个字符")
    return cleaned


def _idempotency_key(value: str) -> str:
    cleaned = _clean(value, label="幂等键", maximum=200, required=True)
    if len(cleaned) < 8:
        raise ValueError("幂等键不能少于 8 个字符")
    return cleaned


def _request_fingerprint(action: str, payload: dict[str, object]) -> str:
    canonical = json.dumps(
        {"action": action, **payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class LearningService:
    def __init__(
        self,
        repository: LearningRepository,
        tutor: HeritageTutor | None = None,
        tutor_request_limit: int | None = None,
    ) -> None:
        self.repository = repository
        self.tutor = tutor or HeritageTutor()
        self.tutor_request_limit = tutor_request_limit or int(
            os.getenv("HAHA_TUTOR_REQUEST_LIMIT_24H", "20")
        )
        if not 1 <= self.tutor_request_limit <= 100:
            raise ValueError("HAHA_TUTOR_REQUEST_LIMIT_24H must be between 1 and 100")

    def bootstrap(self, user_id: str, workspace_id: str) -> dict[str, object]:
        self._require_learner(user_id, workspace_id)
        self.repository.ensure_learning_catalog(workspace_id)
        profile = self.repository.ensure_learning_profile(user_id, workspace_id)
        today = self._activity_date(profile.timezone)
        self.repository.ensure_daily_tasks(user_id, workspace_id, today)
        return self.snapshot(user_id, workspace_id)

    def snapshot(self, user_id: str, workspace_id: str) -> dict[str, object]:
        self._require_learner(user_id, workspace_id)
        self.repository.ensure_learning_catalog(workspace_id)
        profile = self.repository.ensure_learning_profile(user_id, workspace_id)
        today = self._activity_date(profile.timezone)
        self.repository.ensure_daily_tasks(user_id, workspace_id, today)
        paths = self.repository.list_learning_paths(workspace_id)
        sources = self.repository.list_knowledge_sources(workspace_id)
        enrollments = self.repository.list_path_enrollments(user_id, workspace_id)
        progress = self.repository.list_learning_progress(user_id, workspace_id)
        cards = self.repository.list_knowledge_cards(user_id, workspace_id)
        attempts = self.repository.list_quiz_attempts(user_id, workspace_id)
        events = self.repository.list_learning_events(user_id, workspace_id)
        grants = self.repository.list_achievement_grants(user_id, workspace_id)
        tutor_interactions = self.repository.list_tutor_interactions(
            user_id, workspace_id
        )
        definitions = {
            item.id: item
            for item in self.repository.list_achievement_definitions(workspace_id)
        }
        enrollment_by_path = {item.path_id: item for item in enrollments}
        progress_by_unit = {item.unit_id: item for item in progress}
        path_payloads: list[dict[str, object]] = []
        for path in paths:
            units = self.repository.list_learning_units(path.id, workspace_id)
            unit_payloads: list[dict[str, object]] = []
            for unit in units:
                item = asdict(unit)
                item["progress"] = (
                    asdict(progress_by_unit[unit.id])
                    if unit.id in progress_by_unit
                    else {
                        "status": ProgressStatus.NOT_STARTED.value,
                        "progress_percent": 0,
                        "version": 0,
                        "updated_at": "",
                    }
                )
                quiz = self.repository.get_quiz_for_unit(unit.id, workspace_id)
                if quiz:
                    item["quiz"] = {
                        **asdict(quiz),
                        "questions": [
                            {
                                "id": question.id,
                                "position": question.position,
                                "prompt": question.prompt,
                                "choices": json.loads(question.choices_json),
                                "source_id": question.source_id,
                                "version": question.version,
                            }
                            for question in self.repository.list_quiz_questions(
                                quiz.id, workspace_id
                            )
                        ],
                    }
                unit_payloads.append(item)
            required = [item for item in units if item.required]
            completed = sum(
                progress_by_unit.get(item.id) is not None
                and progress_by_unit[item.id].status == ProgressStatus.COMPLETED.value
                for item in required
            )
            path_payloads.append(
                {
                    **asdict(path),
                    "enrollment": asdict(enrollment_by_path[path.id])
                    if path.id in enrollment_by_path
                    else None,
                    "completion_percent": round(100 * completed / len(required))
                    if required
                    else 0,
                    "units": unit_payloads,
                }
            )
        candidates = [
            asdict(item)
            for item in self.repository.list_library_items(user_id, workspace_id)
            if item.kind == LibraryKind.WANT_TO_LEARN.value
        ]
        grant_payloads = []
        for grant in grants:
            definition = definitions.get(grant.definition_id)
            grant_payloads.append(
                {
                    **asdict(grant),
                    "code": definition.code if definition else "unknown",
                    "title": definition.title if definition else "未知成就",
                    "description": definition.description if definition else "",
                    "points": definition.points if definition else 0,
                }
            )
        return {
            "profile": asdict(profile),
            "paths": path_payloads,
            "sources": [asdict(item) for item in sources],
            "learning_candidates": candidates,
            "cards": [asdict(item) for item in cards],
            "quiz_attempts": [asdict(item) for item in attempts],
            "daily_tasks": [
                asdict(item)
                for item in self.repository.list_daily_tasks(
                    user_id, workspace_id, today
                )
            ],
            "achievements": grant_payloads,
            "recent_events": [asdict(item) for item in events[:20]],
            "summary": self.repository.get_learning_growth_summary(
                user_id, workspace_id
            ),
            "ai_tutor": {
                **self.tutor.status(),
                "supported_scope": "仅支持知识库可精确命中的非遗项目；回答保留来源编号、版本与可信状态。",
                "request_limit_24h": self.tutor_request_limit,
            },
            "tutor_history": [
                self._tutor_payload(item)
                for item in tutor_interactions
                if item.status == "completed"
            ],
            "catalog_notice": "当前课程为内部功能验证目录，不构成正式非遗事实、来源认证或权威教学结论。",
        }

    def ask_tutor(
        self,
        user_id: str,
        workspace_id: str,
        *,
        question: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        self._require_learner(user_id, workspace_id)
        clean_question = _clean(
            question, label="问题", maximum=1000, required=True
        )
        if len(clean_question) < 2:
            raise ValueError("问题不能少于 2 个字符")
        clean_key = _idempotency_key(idempotency_key)
        fingerprint = _request_fingerprint(
            "tutor.ask", {"question": clean_question}
        )
        existing = self.repository.find_tutor_interaction(
            user_id, workspace_id, clean_key
        )
        if existing:
            return self._replay_tutor(existing, fingerprint)
        created_after = _timestamp(_now_dt() - timedelta(hours=24))
        if self.repository.count_tutor_interactions_since(
            user_id, workspace_id, created_after
        ) >= self.tutor_request_limit:
            raise LearningTutorRateLimitError(
                f"当前账户 24 小时内最多提交 {self.tutor_request_limit} 次 AI 老师问题"
            )
        status = self.tutor.status()
        if status["status"] != "available":
            raise LearningTutorUnavailableError(str(status["reason"]))

        now = _timestamp()
        pending = TutorInteraction(
            id=_stable_id("tutor", user_id, workspace_id, clean_key),
            user_id=user_id,
            workspace_id=workspace_id,
            idempotency_key=clean_key,
            request_fingerprint=fingerprint,
            question=clean_question,
            status="pending",
            answer="",
            citations_json="{}",
            model="",
            request_id="",
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            error_code="",
            created_at=now,
            updated_at=now,
        )
        if not self.repository.create_tutor_interaction(pending):
            winner = self.repository.find_tutor_interaction(
                user_id, workspace_id, clean_key
            )
            if not winner:
                raise LearningConflictError("AI 老师请求未能安全创建")
            return self._replay_tutor(winner, fingerprint)

        try:
            answer = self.tutor.answer(clean_question)
        except ModelCallError as exc:
            evidence = exc.evidence
            failed = replace(
                pending,
                status="failed",
                model=evidence.model if evidence else str(status.get("model", "")),
                request_id=evidence.request_id if evidence else "",
                input_tokens=evidence.input_tokens if evidence else 0,
                output_tokens=evidence.output_tokens if evidence else 0,
                latency_ms=evidence.latency_ms if evidence else 0,
                error_code="model_call_failed",
                updated_at=_timestamp(),
            )
            self.repository.update_tutor_interaction(failed, "pending")
            raise LearningTutorUnavailableError(str(exc)) from exc

        evidence = answer.evidence
        trace = {
            "citations": [asdict(item) for item in answer.citations],
            "uncertainty": answer.uncertainty,
            "suggested_questions": list(answer.suggested_questions),
            "mode": answer.mode,
        }
        completed = replace(
            pending,
            status="completed",
            answer=answer.answer,
            citations_json=json.dumps(trace, ensure_ascii=False, sort_keys=True),
            model=evidence.model if evidence else "",
            request_id=evidence.request_id if evidence else "",
            input_tokens=evidence.input_tokens if evidence else 0,
            output_tokens=evidence.output_tokens if evidence else 0,
            latency_ms=evidence.latency_ms if evidence else 0,
            updated_at=_timestamp(),
        )
        if not self.repository.update_tutor_interaction(completed, "pending"):
            raise LearningConflictError("AI 老师请求状态已变化，不能覆盖")
        result = self.snapshot(user_id, workspace_id)
        result["last_tutor_result"] = self._tutor_payload(completed)
        return result

    def enroll_path(
        self,
        user_id: str,
        workspace_id: str,
        path_id: str,
        *,
        source_content_id: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        self.bootstrap(user_id, workspace_id)
        idempotency_key = _idempotency_key(idempotency_key)
        source_content = _clean(
            source_content_id, label="想学内容 ID", maximum=200
        )
        request_fingerprint = _request_fingerprint(
            "path.enroll",
            {"path_id": path_id, "source_content_id": source_content},
        )
        existing_event = self.repository.find_learning_event(
            user_id, workspace_id, idempotency_key
        )
        if existing_event:
            self._require_matching_idempotency(existing_event, request_fingerprint)
            return self.snapshot(user_id, workspace_id)
        path = self.repository.get_learning_path(path_id, workspace_id)
        if not path or path.status != "published":
            raise LearningNotFoundError("学习路径不存在或尚未发布")
        existing = self.repository.get_path_enrollment(
            user_id, workspace_id, path_id
        )
        if existing:
            return self.snapshot(user_id, workspace_id)
        if source_content:
            owned = any(
                item.kind == LibraryKind.WANT_TO_LEARN.value
                and item.target_id == source_content
                for item in self.repository.list_library_items(user_id, workspace_id)
            )
            if not owned:
                raise LearningPermissionError("想学内容不属于当前账户")
        now = _timestamp()
        enrollment = PathEnrollment(
            id=_stable_id("enrollment", user_id, workspace_id, path_id),
            user_id=user_id,
            workspace_id=workspace_id,
            path_id=path_id,
            source_content_id=source_content,
            status=EnrollmentStatus.ACTIVE.value,
            version=1,
            enrolled_at=now,
            completed_at="",
            updated_at=now,
        )
        event = self._event(
            user_id,
            workspace_id,
            event_type="path.enrolled",
            entity_type="learning_path",
            entity_id=path.id,
            entity_version=path.version,
            idempotency_key=idempotency_key,
            payload={
                "source_content_id": source_content,
                "request_fingerprint": request_fingerprint,
            },
        )
        self.repository.commit_learning_activity(
            LearningActivityCommit(event=event, enrollment=enrollment)
        )
        return self.snapshot(user_id, workspace_id)

    def complete_unit(
        self,
        user_id: str,
        workspace_id: str,
        unit_id: str,
        *,
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, object]:
        self.bootstrap(user_id, workspace_id)
        idempotency_key = _idempotency_key(idempotency_key)
        request_fingerprint = _request_fingerprint(
            "unit.complete",
            {"unit_id": unit_id, "expected_version": expected_version},
        )
        existing_event = self.repository.find_learning_event(
            user_id, workspace_id, idempotency_key
        )
        if existing_event:
            self._require_matching_idempotency(existing_event, request_fingerprint)
            return self.snapshot(user_id, workspace_id)
        unit = self.repository.get_learning_unit(unit_id, workspace_id)
        if not unit:
            raise LearningNotFoundError("学习节点不存在")
        if unit.kind == "quiz":
            raise LearningConflictError("测验节点只能通过提交答案完成")
        if not self.repository.get_path_enrollment(
            user_id, workspace_id, unit.path_id
        ):
            raise LearningPermissionError("请先加入该学习路径")
        current = self.repository.get_learning_progress(
            user_id, workspace_id, unit.id
        )
        current_version = current.version if current else 0
        if current and current.status == ProgressStatus.COMPLETED.value:
            return self.snapshot(user_id, workspace_id)
        if expected_version != current_version:
            raise LearningConflictError("学习进度版本已变化，请刷新后重试")
        now = _timestamp()
        progress = LearningProgress(
            id=current.id
            if current
            else _stable_id("progress", user_id, workspace_id, unit.id),
            user_id=user_id,
            workspace_id=workspace_id,
            path_id=unit.path_id,
            unit_id=unit.id,
            status=ProgressStatus.COMPLETED.value,
            progress_percent=100,
            version=current_version + 1,
            started_at=current.started_at if current and current.started_at else now,
            completed_at=now,
            updated_at=now,
        )
        event = self._event(
            user_id,
            workspace_id,
            event_type="unit.completed",
            entity_type="learning_unit",
            entity_id=unit.id,
            entity_version=progress.version,
            idempotency_key=idempotency_key,
            payload={
                "path_id": unit.path_id,
                "request_fingerprint": request_fingerprint,
            },
        )
        self.repository.commit_learning_activity(
            LearningActivityCommit(
                event=event,
                progress=progress,
                expected_progress_version=expected_version,
                refresh_path_id=unit.path_id,
            )
        )
        return self.snapshot(user_id, workspace_id)

    def save_knowledge_card(
        self,
        user_id: str,
        workspace_id: str,
        unit_id: str,
        *,
        topic: str,
        body: str,
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, object]:
        self.bootstrap(user_id, workspace_id)
        idempotency_key = _idempotency_key(idempotency_key)
        clean_topic = _clean(
            topic, label="知识卡主题", maximum=200, required=True
        )
        clean_body = _clean(
            body, label="知识卡内容", maximum=4000, required=True
        )
        request_fingerprint = _request_fingerprint(
            "knowledge_card.upsert",
            {
                "unit_id": unit_id,
                "topic": clean_topic,
                "body": clean_body,
                "expected_version": expected_version,
            },
        )
        existing_event = self.repository.find_learning_event(
            user_id, workspace_id, idempotency_key
        )
        if existing_event:
            self._require_matching_idempotency(existing_event, request_fingerprint)
            return self.snapshot(user_id, workspace_id)
        unit = self.repository.get_learning_unit(unit_id, workspace_id)
        if not unit:
            raise LearningNotFoundError("知识节点不存在")
        if not self.repository.get_path_enrollment(
            user_id, workspace_id, unit.path_id
        ):
            raise LearningPermissionError("请先加入该学习路径")
        source = self.repository.get_knowledge_source(unit.source_id, workspace_id)
        if not source:
            raise LearningConflictError("知识节点缺少可追溯来源")
        current = self.repository.get_knowledge_card(
            user_id, workspace_id, unit.id
        )
        current_version = current.version if current else 0
        if expected_version != current_version:
            raise LearningConflictError("知识卡版本已变化，请刷新后重试")
        now = _timestamp()
        card = KnowledgeCard(
            id=current.id
            if current
            else _stable_id("card", user_id, workspace_id, unit.id),
            user_id=user_id,
            workspace_id=workspace_id,
            path_id=unit.path_id,
            unit_id=unit.id,
            topic=clean_topic,
            body=clean_body,
            source_id=source.id,
            source_version=source.version,
            trust_status=source.verification_status,
            version=current_version + 1,
            created_at=current.created_at if current else now,
            updated_at=now,
        )
        event_type = "knowledge_card.updated" if current else "knowledge_card.saved"
        event = self._event(
            user_id,
            workspace_id,
            event_type=event_type,
            entity_type="knowledge_card",
            entity_id=card.id,
            entity_version=card.version,
            idempotency_key=idempotency_key,
            payload={
                "unit_id": unit.id,
                "source_id": source.id,
                "source_version": source.version,
                "trust_status": source.verification_status,
                "request_fingerprint": request_fingerprint,
            },
        )
        self.repository.commit_learning_activity(
            LearningActivityCommit(
                event=event,
                card=card,
                expected_card_version=expected_version,
            )
        )
        return self.snapshot(user_id, workspace_id)

    def submit_quiz(
        self,
        user_id: str,
        workspace_id: str,
        quiz_id: str,
        *,
        answers: dict[str, int],
        expected_progress_version: int,
        idempotency_key: str,
    ) -> dict[str, object]:
        self.bootstrap(user_id, workspace_id)
        idempotency_key = _idempotency_key(idempotency_key)
        request_fingerprint = _request_fingerprint(
            "quiz.submit",
            {
                "quiz_id": quiz_id,
                "answers": answers,
                "expected_progress_version": expected_progress_version,
            },
        )
        existing_event = self.repository.find_learning_event(
            user_id, workspace_id, idempotency_key
        )
        if existing_event:
            self._require_matching_idempotency(existing_event, request_fingerprint)
            return self.snapshot(user_id, workspace_id)
        quiz = self.repository.get_quiz(quiz_id, workspace_id)
        if not quiz or quiz.status != "published":
            raise LearningNotFoundError("测验不存在或尚未发布")
        if not self.repository.get_path_enrollment(
            user_id, workspace_id, quiz.path_id
        ):
            raise LearningPermissionError("请先加入该学习路径")
        questions = self.repository.list_quiz_questions(quiz.id, workspace_id)
        expected_ids = {item.id for item in questions}
        if set(answers) != expected_ids:
            raise ValueError("必须回答测验中的全部题目，且不能提交未知题目")
        if any(
            not isinstance(value, int)
            or value < 0
            or value >= len(json.loads(question.choices_json))
            for question in questions
            for value in [answers[question.id]]
        ):
            raise ValueError("答案选项无效")
        correct = sum(answers[item.id] == item.correct_choice for item in questions)
        score = round(100 * correct / len(questions)) if questions else 0
        passed = score >= quiz.pass_score
        now = _timestamp()
        attempt = QuizAttempt(
            id=_stable_id("attempt", user_id, workspace_id, idempotency_key),
            user_id=user_id,
            workspace_id=workspace_id,
            quiz_id=quiz.id,
            quiz_version=quiz.version,
            answers_json=json.dumps(answers, ensure_ascii=False, sort_keys=True),
            question_snapshot_json=json.dumps(
                [
                    {
                        "id": item.id,
                        "prompt": item.prompt,
                        "choices": json.loads(item.choices_json),
                        "correct_choice": item.correct_choice,
                        "explanation": item.explanation,
                        "source_id": item.source_id,
                        "version": item.version,
                    }
                    for item in questions
                ],
                ensure_ascii=False,
                sort_keys=True,
            ),
            score=score,
            passed=passed,
            created_at=now,
        )
        current = self.repository.get_learning_progress(
            user_id, workspace_id, quiz.unit_id
        )
        current_version = current.version if current else 0
        if expected_progress_version != current_version:
            raise LearningConflictError("测验节点进度版本已变化，请刷新后重试")
        progress = None
        if passed and not (
            current and current.status == ProgressStatus.COMPLETED.value
        ):
            progress = LearningProgress(
                id=current.id
                if current
                else _stable_id("progress", user_id, workspace_id, quiz.unit_id),
                user_id=user_id,
                workspace_id=workspace_id,
                path_id=quiz.path_id,
                unit_id=quiz.unit_id,
                status=ProgressStatus.COMPLETED.value,
                progress_percent=100,
                version=current_version + 1,
                started_at=current.started_at if current and current.started_at else now,
                completed_at=now,
                updated_at=now,
            )
        event = self._event(
            user_id,
            workspace_id,
            event_type="quiz.passed" if passed else "quiz.attempted",
            entity_type="quiz_attempt",
            entity_id=attempt.id,
            entity_version=quiz.version,
            idempotency_key=idempotency_key,
            payload={
                "quiz_id": quiz.id,
                "score": score,
                "passed": passed,
                "request_fingerprint": request_fingerprint,
            },
        )
        self.repository.commit_learning_activity(
            LearningActivityCommit(
                event=event,
                attempt=attempt,
                progress=progress,
                expected_progress_version=(
                    expected_progress_version if progress else None
                ),
                refresh_path_id=quiz.path_id if progress else "",
            )
        )
        result = self.snapshot(user_id, workspace_id)
        result["last_quiz_result"] = {
            "attempt_id": attempt.id,
            "score": score,
            "passed": passed,
            "correct": correct,
            "total": len(questions),
        }
        return result

    def _replay_tutor(
        self, interaction: TutorInteraction, request_fingerprint: str
    ) -> dict[str, object]:
        if interaction.request_fingerprint != request_fingerprint:
            raise LearningConflictError("幂等键已用于不同的 AI 老师问题")
        if interaction.status == "pending":
            raise LearningConflictError("AI 老师正在处理该请求，请稍后使用同一幂等键重试")
        if interaction.status == "failed":
            raise LearningTutorUnavailableError("此前同一请求调用失败，请使用新的幂等键重试")
        result = self.snapshot(interaction.user_id, interaction.workspace_id)
        result["last_tutor_result"] = self._tutor_payload(interaction)
        return result

    @staticmethod
    def _tutor_payload(interaction: TutorInteraction) -> dict[str, object]:
        try:
            trace = json.loads(interaction.citations_json or "{}")
        except json.JSONDecodeError:
            trace = {}
        return {
            "id": interaction.id,
            "question": interaction.question,
            "status": interaction.status,
            "answer": interaction.answer,
            "citations": trace.get("citations", []),
            "uncertainty": trace.get("uncertainty", ""),
            "suggested_questions": trace.get("suggested_questions", []),
            "mode": trace.get("mode", ""),
            "model": interaction.model,
            "request_id": interaction.request_id,
            "input_tokens": interaction.input_tokens,
            "output_tokens": interaction.output_tokens,
            "latency_ms": interaction.latency_ms,
            "created_at": interaction.created_at,
        }

    def _require_learner(self, user_id: str, workspace_id: str) -> None:
        if not any(
            item.role == "learner" and item.status == "active"
            for item in self.repository.list_role_grants(user_id, workspace_id)
        ):
            raise LearningPermissionError("当前账户未开通学习者身份")

    @staticmethod
    def _require_matching_idempotency(
        event: LearningEvent, request_fingerprint: str
    ) -> None:
        try:
            stored = json.loads(event.payload_json).get("request_fingerprint", "")
        except (json.JSONDecodeError, AttributeError) as exc:
            raise LearningConflictError("幂等记录损坏，不能安全重放请求") from exc
        if stored != request_fingerprint:
            raise LearningConflictError("幂等键已用于不同的学习请求")

    def _event(
        self,
        user_id: str,
        workspace_id: str,
        *,
        event_type: str,
        entity_type: str,
        entity_id: str,
        entity_version: int,
        idempotency_key: str,
        payload: dict[str, object],
    ) -> LearningEvent:
        profile = self.repository.ensure_learning_profile(user_id, workspace_id)
        now = _now_dt()
        return LearningEvent(
            id=_stable_id("levent", user_id, workspace_id, idempotency_key),
            user_id=user_id,
            workspace_id=workspace_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_version=entity_version,
            idempotency_key=idempotency_key,
            activity_date=self._activity_date(profile.timezone, now),
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            created_at=_timestamp(now),
        )

    @staticmethod
    def _activity_date(timezone_name: str, value: datetime | None = None) -> str:
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise LearningConflictError("学习档案时区无效") from exc
        return (value or _now_dt()).astimezone(zone).date().isoformat()
