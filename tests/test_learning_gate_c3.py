from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from haha_api.main import create_app
from haha_core.repository import SQLiteCreatorRepository
from haha_core.sqlalchemy_repository import SQLAlchemyCreatorRepository
from haha_identity.service import IdentityService
from haha_learning.domain import LearningConflictError, LearningPermissionError
from haha_learning.seed import LESSON_UNIT_ID, PATH_ID, QUIZ_ID, QUIZ_UNIT_ID
from haha_learning.service import LearningService
from haha_user_center.service import UserCenterService


def _repository() -> SQLiteCreatorRepository:
    repository = SQLiteCreatorRepository(":memory:")
    repository.ensure_identity("learner-a", "workspace-a", role="owner")
    repository.ensure_identity("member-b", "workspace-a", role="viewer")
    IdentityService(repository).bootstrap("learner-a", "workspace-a")
    return repository


def _correct_answers(snapshot: dict[str, object]) -> dict[str, int]:
    paths = snapshot["paths"]
    assert isinstance(paths, list)
    quiz_unit = next(
        unit
        for path in paths
        for unit in path["units"]
        if unit["id"] == QUIZ_UNIT_ID
    )
    return {item["id"]: 1 for item in quiz_unit["quiz"]["questions"]}


def test_learning_requires_workspace_membership_and_grants_default_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    repository = _repository()
    service = LearningService(repository)

    with pytest.raises(LearningPermissionError, match="没有学习中心访问权限"):
        service.bootstrap("outsider", "workspace-a")

    snapshot = service.bootstrap("member-b", "workspace-a")
    assert "learner" in {
        item.role for item in repository.list_role_grants("member-b", "workspace-a")
    }
    assert snapshot["ai_tutor"]["status"] == "blocked"
    assert snapshot["paths"][0]["verification_status"] == "demo_only"


def test_complete_learning_loop_is_durable_idempotent_and_auditable() -> None:
    repository = _repository()
    center = UserCenterService(repository)
    center.bootstrap("learner-a", "workspace-a")
    center.set_library_item(
        "learner-a",
        "workspace-a",
        kind_value="want_to_learn",
        target_id="content-embroidery-01",
        title="一根线，怎样绣出远方？",
        target_href="/content/content-embroidery-01",
        active=True,
    )
    service = LearningService(repository)
    initial = service.bootstrap("learner-a", "workspace-a")
    assert initial["learning_candidates"][0]["target_id"] == "content-embroidery-01"
    assert len(initial["daily_tasks"]) == 3

    enrolled = service.enroll_path(
        "learner-a",
        "workspace-a",
        PATH_ID,
        source_content_id="content-embroidery-01",
        idempotency_key="enroll-path-0001",
    )
    assert enrolled["paths"][0]["enrollment"]["status"] == "active"

    completed = service.complete_unit(
        "learner-a",
        "workspace-a",
        LESSON_UNIT_ID,
        expected_version=0,
        idempotency_key="complete-unit-0001",
    )
    lesson = next(
        unit for unit in completed["paths"][0]["units"] if unit["id"] == LESSON_UNIT_ID
    )
    assert lesson["progress"]["status"] == "completed"
    assert lesson["progress"]["version"] == 1

    with_card = service.save_knowledge_card(
        "learner-a",
        "workspace-a",
        LESSON_UNIT_ID,
        topic="如何判断资料可信状态",
        body="保留来源、版本与可信状态；待核验资料不能当作已确认事实。",
        expected_version=0,
        idempotency_key="save-card-000001",
    )
    assert with_card["cards"][0]["source_version"] == 1
    assert with_card["cards"][0]["trust_status"] == "demo_only"

    answers = _correct_answers(with_card)
    finished = service.submit_quiz(
        "learner-a",
        "workspace-a",
        QUIZ_ID,
        answers=answers,
        expected_progress_version=0,
        idempotency_key="quiz-attempt-0001",
    )
    assert finished["last_quiz_result"]["passed"] is True
    assert finished["last_quiz_result"]["score"] == 100
    assert finished["paths"][0]["enrollment"]["status"] == "completed"
    assert finished["paths"][0]["completion_percent"] == 100
    assert all(item["status"] == "completed" for item in finished["daily_tasks"])
    assert finished["summary"]["current_streak"] == 1
    assert finished["summary"]["achievements"] == 3
    assert finished["summary"]["achievement_points"] == 40
    assert len(finished["quiz_attempts"]) == 1

    repeated = service.submit_quiz(
        "learner-a",
        "workspace-a",
        QUIZ_ID,
        answers=answers,
        expected_progress_version=0,
        idempotency_key="quiz-attempt-0001",
    )
    assert len(repeated["quiz_attempts"]) == 1
    assert repeated["summary"]["achievements"] == 3
    with pytest.raises(LearningConflictError, match="幂等键已用于不同"):
        service.submit_quiz(
            "learner-a",
            "workspace-a",
            QUIZ_ID,
            answers={question_id: 0 for question_id in answers},
            expected_progress_version=0,
            idempotency_key="quiz-attempt-0001",
        )

    reloaded = LearningService(repository).bootstrap("learner-a", "workspace-a")
    assert reloaded["paths"][0]["completion_percent"] == 100
    assert reloaded["summary"]["knowledge_cards"] == 1
    growth = center.snapshot("learner-a", "workspace-a")["growth"]
    assert growth["completed_units"] == 2
    assert growth["achievements"] == 3
    assert growth["current_streak"] == 1

    attempts = repository.list_quiz_attempts("learner-a", "workspace-a")
    snapshot_questions = json.loads(attempts[0].question_snapshot_json)
    assert snapshot_questions[0]["correct_choice"] == 1
    assert attempts[0].answers_json == json.dumps(answers, ensure_ascii=False, sort_keys=True)


def test_card_versions_and_learning_candidate_ownership_fail_closed() -> None:
    repository = _repository()
    center = UserCenterService(repository)
    center.bootstrap("learner-a", "workspace-a")
    center.bootstrap("member-b", "workspace-a")
    center.set_library_item(
        "learner-a", "workspace-a", kind_value="want_to_learn",
        target_id="content-private", title="账户 A 的想学内容",
        target_href="/content/content-private", active=True,
    )
    service = LearningService(repository)
    service.bootstrap("learner-a", "workspace-a")
    service.bootstrap("member-b", "workspace-a")

    with pytest.raises(LearningPermissionError, match="不属于当前账户"):
        service.enroll_path(
            "member-b", "workspace-a", PATH_ID,
            source_content_id="content-private", idempotency_key="member-b-enroll-01",
        )

    service.enroll_path(
        "learner-a", "workspace-a", PATH_ID,
        source_content_id="content-private", idempotency_key="learner-enroll-001",
    )
    service.save_knowledge_card(
        "learner-a", "workspace-a", LESSON_UNIT_ID,
        topic="第一版", body="带来源的第一版知识卡。", expected_version=0,
        idempotency_key="learner-card-0001",
    )
    with pytest.raises(LearningConflictError, match="知识卡版本"):
        service.save_knowledge_card(
            "learner-a", "workspace-a", LESSON_UNIT_ID,
            topic="过期写入", body="不能覆盖已经存在的版本。", expected_version=0,
            idempotency_key="learner-card-stale",
        )
    with pytest.raises(LearningConflictError, match="测验节点"):
        service.complete_unit(
            "learner-a", "workspace-a", QUIZ_UNIT_ID,
            expected_version=0, idempotency_key="quiz-direct-complete",
        )


def test_learning_api_permission_idempotency_and_server_grading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    repository = _repository()
    client = TestClient(create_app(repository))
    headers_a = {"X-User-ID": "learner-a", "X-Workspace-ID": "workspace-a"}
    ordinary_account = {"X-User-ID": "ordinary", "X-Workspace-ID": "workspace-a"}

    assert client.get(
        "/api/learning?role=learner", headers=ordinary_account
    ).status_code == 200
    snapshot = client.get("/api/learning", headers=headers_a)
    assert snapshot.status_code == 200
    assert snapshot.json()["ai_tutor"]["status"] == "blocked"
    assert client.post(
        f"/api/learning/paths/{PATH_ID}/enroll",
        headers=headers_a,
        json={"source_content_id": ""},
    ).status_code == 422

    write_headers = {**headers_a, "Idempotency-Key": "api-enroll-000001"}
    assert client.post(
        f"/api/learning/paths/{PATH_ID}/enroll",
        headers=write_headers,
        json={"source_content_id": ""},
    ).status_code == 200
    complete = client.post(
        f"/api/learning/units/{LESSON_UNIT_ID}/complete",
        headers={**headers_a, "Idempotency-Key": "api-unit-0000001"},
        json={"expected_version": 0},
    )
    assert complete.status_code == 200
    answers = _correct_answers(complete.json())
    attempt = client.post(
        f"/api/learning/quizzes/{QUIZ_ID}/attempts",
        headers={**headers_a, "Idempotency-Key": "api-quiz-0000001"},
        json={"answers": answers, "expected_progress_version": 0},
    )
    assert attempt.status_code == 200
    assert attempt.json()["last_quiz_result"]["passed"] is True


def test_sqlalchemy_learning_adapter_persists_the_same_transactional_loop() -> None:
    repository = SQLAlchemyCreatorRepository(
        "sqlite+pysqlite:///:memory:", create_schema=True
    )
    repository.ensure_identity("sa-learner", "sa-workspace", role="owner")
    identity = IdentityService(repository)
    identity.bootstrap("sa-learner", "sa-workspace")
    service = LearningService(repository)

    service.bootstrap("sa-learner", "sa-workspace")
    service.enroll_path(
        "sa-learner",
        "sa-workspace",
        PATH_ID,
        source_content_id="",
        idempotency_key="sa-enroll-000001",
    )
    completed = service.complete_unit(
        "sa-learner",
        "sa-workspace",
        LESSON_UNIT_ID,
        expected_version=0,
        idempotency_key="sa-unit-0000001",
    )
    answers = _correct_answers(completed)
    service.submit_quiz(
        "sa-learner",
        "sa-workspace",
        QUIZ_ID,
        answers=answers,
        expected_progress_version=0,
        idempotency_key="sa-quiz-0000001",
    )

    restored = LearningService(repository).bootstrap("sa-learner", "sa-workspace")
    assert restored["paths"][0]["completion_percent"] == 100
    assert restored["summary"]["completed_units"] == 2
    assert restored["summary"]["achievements"] == 2
