"""HTTP acceptance for Gate C3 against the real PostgreSQL-backed stack."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "e2e" / "learning-gate-c3-api"
STATE_FILE = ARTIFACTS / "state.json"
REPORT_FILE = ARTIFACTS / "report.json"
API_URL = os.getenv("HAHA_E2E_API_URL", "http://127.0.0.1:8000").rstrip("/")


def request(
    method: str,
    path: str,
    user_id: str,
    workspace_id: str,
    payload: dict[str, object] | None = None,
    idempotency_key: str = "",
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    headers = {
        "Accept": "application/json",
        "X-User-ID": user_id,
        "X-Workspace-ID": workspace_id,
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    call = urllib.request.Request(
        f"{API_URL}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(call, timeout=20) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            detail = json.loads(body) if body else None
        except json.JSONDecodeError:
            detail = body.decode(errors="replace")
        return exc.code, detail


def exercise() -> dict[str, object]:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    suffix = uuid4().hex[:10]
    user_id = f"c3-learner-{suffix}"
    outsider = f"c3-outsider-{suffix}"
    workspace_id = f"c3-learning-{suffix}"
    assertions: dict[str, bool] = {}

    assertions["non_learner_denied"] = request(
        "GET", "/api/learning", outsider, workspace_id
    )[0] == 403
    assertions["learner_activated"] = request(
        "POST", "/api/identity/roles/learner/activate", user_id, workspace_id
    )[0] == 200
    status, snapshot = request("GET", "/api/learning", user_id, workspace_id)
    assertions["catalog_is_honest"] = (
        status == 200
        and snapshot["ai_tutor"]["status"] == "available"
        and snapshot["paths"][0]["verification_status"] == "demo_only"
    )
    status, tutor_answer = request(
        "POST", "/api/learning/tutor/questions", user_id, workspace_id,
        {"question": "中国剪纸有哪些主要特点？"}, "c3-api-tutor-000001",
    )
    tutor_result = tutor_answer.get("last_tutor_result", {}) if status == 200 else {}
    assertions["real_tutor_grounded"] = (
        status == 200
        and tutor_result.get("mode") == "grounded_model"
        and tutor_result.get("request_id")
        and tutor_result.get("input_tokens", 0) > 0
        and any(item.get("source_id") == "F-096" for item in tutor_result.get("citations", []))
    )
    _, tutor_replay = request(
        "POST", "/api/learning/tutor/questions", user_id, workspace_id,
        {"question": "中国剪纸有哪些主要特点？"}, "c3-api-tutor-000001",
    )
    assertions["tutor_idempotent_retry"] = (
        tutor_replay.get("last_tutor_result", {}).get("id") == tutor_result.get("id")
    )
    assertions["tutor_idempotency_conflict"] = request(
        "POST", "/api/learning/tutor/questions", user_id, workspace_id,
        {"question": "昆曲的表演特点是什么？"}, "c3-api-tutor-000001",
    )[0] == 409
    status, no_source = request(
        "POST", "/api/learning/tutor/questions", user_id, workspace_id,
        {"question": "一个知识库里不存在的技艺是什么？"}, "c3-api-tutor-nosource",
    )
    assertions["tutor_unknown_entity_fail_closed"] = (
        status == 200
        and no_source.get("last_tutor_result", {}).get("mode") == "no_sources"
        and no_source.get("last_tutor_result", {}).get("input_tokens") == 0
    )
    path = snapshot["paths"][0]
    lesson = next(item for item in path["units"] if item["kind"] == "lesson")
    quiz_unit = next(item for item in path["units"] if item["kind"] == "quiz")
    quiz = quiz_unit["quiz"]

    status, _ = request(
        "POST", f"/api/learning/paths/{path['id']}/enroll", user_id, workspace_id,
        {"source_content_id": ""}, "c3-api-enroll-0001",
    )
    assertions["path_enrolled"] = status == 200
    status, _ = request(
        "POST", f"/api/learning/units/{lesson['id']}/complete", user_id, workspace_id,
        {"expected_version": 0}, "c3-api-unit-000001",
    )
    assertions["unit_completed"] = status == 200
    status, _ = request(
        "PUT", f"/api/learning/cards/{lesson['id']}", user_id, workspace_id,
        {
            "topic": "真实环境来源检查",
            "body": "保留来源、版本和可信状态；待核验资料不当作正式事实。",
            "expected_version": 0,
        },
        "c3-api-card-000001",
    )
    assertions["knowledge_card_saved"] = status == 200

    wrong_answers = {item["id"]: 0 for item in quiz["questions"]}
    status, failed = request(
        "POST", f"/api/learning/quizzes/{quiz['id']}/attempts", user_id, workspace_id,
        {"answers": wrong_answers, "expected_progress_version": 0},
        "c3-api-quiz-fail-01",
    )
    assertions["server_rejected_wrong_answers"] = (
        status == 200 and failed["last_quiz_result"]["passed"] is False
    )
    correct_answers = {item["id"]: 1 for item in quiz["questions"]}
    status, passed = request(
        "POST", f"/api/learning/quizzes/{quiz['id']}/attempts", user_id, workspace_id,
        {"answers": correct_answers, "expected_progress_version": 0},
        "c3-api-quiz-pass-01",
    )
    assertions["server_graded_pass"] = (
        status == 200 and passed["last_quiz_result"]["score"] == 100
    )
    _, repeated = request(
        "POST", f"/api/learning/quizzes/{quiz['id']}/attempts", user_id, workspace_id,
        {"answers": correct_answers, "expected_progress_version": 0},
        "c3-api-quiz-pass-01",
    )
    assertions["idempotent_retry"] = (
        len(repeated["quiz_attempts"]) == 2
        and repeated["summary"]["achievements"] == 3
    )
    assertions["idempotency_payload_conflict"] = request(
        "POST", f"/api/learning/quizzes/{quiz['id']}/attempts", user_id, workspace_id,
        {"answers": wrong_answers, "expected_progress_version": 0},
        "c3-api-quiz-pass-01",
    )[0] == 409
    if not all(assertions.values()):
        raise RuntimeError({key: value for key, value in assertions.items() if not value})
    state = {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "exercise_assertions": assertions,
    }
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"phase": "exercise", "status": "passed", "assertions": assertions, **state}
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def verify() -> dict[str, object]:
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    user_id = state["user_id"]
    workspace_id = state["workspace_id"]
    status, snapshot = request("GET", "/api/learning", user_id, workspace_id)
    center_status, center = request("GET", "/api/user-center", user_id, workspace_id)
    assertions = {
        "learning_restored_after_restart": status == 200,
        "path_completion_restored": snapshot["paths"][0]["completion_percent"] == 100,
        "immutable_attempts_restored": len(snapshot["quiz_attempts"]) == 2,
        "daily_tasks_event_driven": all(item["status"] == "completed" for item in snapshot["daily_tasks"]),
        "achievements_granted_once": snapshot["summary"]["achievements"] == 3,
        "streak_restored": snapshot["summary"]["current_streak"] == 1,
        "user_center_growth_synced": (
            center_status == 200
            and center["growth"]["completed_units"] == 2
            and center["growth"]["achievements"] == 3
        ),
        "ai_teacher_available": snapshot["ai_tutor"]["status"] == "available",
        "tutor_history_restored": (
            len(snapshot["tutor_history"]) == 2
            and any(item["mode"] == "grounded_model" for item in snapshot["tutor_history"])
        ),
    }
    if not all(assertions.values()):
        raise RuntimeError({key: value for key, value in assertions.items() if not value})
    report = {
        "phase": "verify-after-restart",
        "status": "passed",
        "exercise_assertions": state.get("exercise_assertions", {}),
        "restart_assertions": assertions,
        "user_id": user_id,
        "workspace_id": workspace_id,
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("exercise", "verify"), default="exercise")
    args = parser.parse_args()
    report = exercise() if args.phase == "exercise" else verify()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
