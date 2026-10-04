from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from haha_core.domain import RunStatus, ScriptVersion, new_id, utc_now
from haha_core.repository import SQLiteCreatorRepository
from haha_core.service import CreatorService, IdempotencyConflictError
from haha_core.verifier import verify_script
from haha_media.script_writer import ContentBrief, generate_content_script


def _service() -> CreatorService:
    return CreatorService(SQLiteCreatorRepository(":memory:"))


def _brief(service: CreatorService, project_id: str, **changes: str):
    data = {
        "craft": "中国剪纸",
        "story_seed": "剪刀落下形成纹样",
        "audience": "传统文化初学者",
        "platform": "B站",
        "tone": "纪录片",
        "goal": "文化科普",
        "duration": "90秒",
        "aspect_ratio": "16:9",
        "asset_context": "",
    }
    data.update(changes)
    return service.create_brief(project_id, **data)


def test_immutable_brief_run_and_script_version_pipeline() -> None:
    service = _service()
    project = service.create_project(title="剪纸专题", workspace_id="ws_test")
    brief = _brief(service, project.id)
    run, created = service.create_run(
        workspace_id="ws_test",
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="本地演示",
        idempotency_key="test-run-0001",
    )
    assert created is True
    completed = service.execute_run(run.id)
    assert completed.status is RunStatus.PASSED
    script = service.repository.get_script_for_run(run.id)
    assert script is not None
    assert script.payload["judgment"][3] == ["推荐平台", "B站"]
    assert script.payload["judgment"][4] == ["推荐规格", "90秒 · 16:9"]
    assert script.evidence["verification"]["passed"] is True


def test_idempotency_key_prevents_duplicate_runs() -> None:
    service = _service()
    project = service.create_project(title="扎染专题", workspace_id="ws_test")
    brief = _brief(service, project.id, craft="白族扎染")
    first, first_created = service.create_run(
        workspace_id="ws_test",
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="本地演示",
        idempotency_key="same-request-001",
    )
    second, second_created = service.create_run(
        workspace_id="ws_test",
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="本地演示",
        idempotency_key="same-request-001",
    )
    assert first_created is True
    assert second_created is False
    assert first.id == second.id


def test_same_key_different_request_returns_conflict() -> None:
    service = _service()
    project = service.create_project(title="幂等冲突", workspace_id="ws_test")
    first_brief = _brief(service, project.id)
    second_brief = _brief(service, project.id, duration="30秒")
    service.create_run(
        workspace_id="ws_test",
        project_id=project.id,
        brief_version_id=first_brief.id,
        model_preference="本地演示",
        idempotency_key="reused-key",
    )
    with pytest.raises(IdempotencyConflictError):
        service.create_run(
            workspace_id="ws_test",
            project_id=project.id,
            brief_version_id=second_brief.id,
            model_preference="本地演示",
            idempotency_key="reused-key",
        )


def test_same_key_is_isolated_across_workspaces_and_projects() -> None:
    service = _service()
    project_a = service.create_project(title="A", workspace_id="ws_a")
    project_b = service.create_project(title="B", workspace_id="ws_b")
    brief_a = _brief(service, project_a.id)
    brief_b = _brief(service, project_b.id)
    run_a, _ = service.create_run(
        workspace_id="ws_a", project_id=project_a.id, brief_version_id=brief_a.id,
        model_preference="本地演示", idempotency_key="shared-key",
    )
    run_b, _ = service.create_run(
        workspace_id="ws_b", project_id=project_b.id, brief_version_id=brief_b.id,
        model_preference="本地演示", idempotency_key="shared-key",
    )
    assert run_a.id != run_b.id


def test_concurrent_same_key_creates_single_run() -> None:
    database_path = Path(".test-artifacts") / f"concurrency-{uuid4().hex}.db"
    service = CreatorService(SQLiteCreatorRepository(database_path))
    project = service.create_project(title="并发幂等", workspace_id="ws_test")
    brief = _brief(service, project.id)

    def submit():
        return service.create_run(
            workspace_id="ws_test",
            project_id=project.id,
            brief_version_id=brief.id,
            model_preference="本地演示",
            idempotency_key="concurrent-key",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(), range(2)))
    assert len({run.id for run, _ in results}) == 1
    assert sorted(created for _, created in results) == [False, True]
    database_path.unlink(missing_ok=True)


def test_two_workers_cannot_claim_same_run() -> None:
    service = _service()
    project = service.create_project(title="领取竞争", workspace_id="ws_test")
    brief = _brief(service, project.id)
    run, _ = service.create_run(
        workspace_id="ws_test", project_id=project.id, brief_version_id=brief.id,
        model_preference="本地演示", idempotency_key="claim-once",
    )
    first = service.repository.claim_run(run.id, "worker-a")
    second = service.repository.claim_run(run.id, "worker-b")
    assert first is not None
    assert first.status is RunStatus.CLAIMED
    assert second is None


def test_expired_lease_can_be_reclaimed_and_heartbeat_extends_it() -> None:
    service = _service()
    project = service.create_project(title="租约恢复", workspace_id="ws_test")
    brief = _brief(service, project.id)
    run, _ = service.create_run(
        workspace_id="ws_test", project_id=project.id, brief_version_id=brief.id,
        model_preference="本地演示", idempotency_key="expired-lease",
    )
    expired = service.repository.claim_run(run.id, "worker-a", lease_seconds=-1)
    reclaimed = service.repository.claim_run(run.id, "worker-b", lease_seconds=30)
    assert expired is not None
    assert reclaimed is not None
    assert reclaimed.claimed_by == "worker-b"
    old_lease = reclaimed.lease_until
    assert service.repository.heartbeat_run(run.id, "worker-b", lease_seconds=60)
    refreshed = service.repository.get_run(run.id)
    assert refreshed is not None
    assert refreshed.lease_until > old_lease


def test_finished_run_cannot_be_reclaimed() -> None:
    service = _service()
    project = service.create_project(title="终态隔离", workspace_id="ws_test")
    brief = _brief(service, project.id)
    run, _ = service.create_run(
        workspace_id="ws_test", project_id=project.id, brief_version_id=brief.id,
        model_preference="本地演示", idempotency_key="terminal-run",
    )
    completed = service.execute_run(run.id, worker_id="worker-a")
    assert completed.status is RunStatus.PASSED
    assert service.repository.claim_run(run.id, "worker-b") is None


def test_transaction_failure_rolls_back_script_and_run() -> None:
    repository = SQLiteCreatorRepository(":memory:")
    service = CreatorService(repository)
    project = service.create_project(title="事务回滚", workspace_id="ws_test")
    brief = _brief(service, project.id)
    run, _ = service.create_run(
        workspace_id="ws_test", project_id=project.id, brief_version_id=brief.id,
        model_preference="本地演示", idempotency_key="atomic-completion",
    )
    claimed = repository.claim_run(run.id, "worker-a")
    assert claimed is not None
    passed = claimed.transition(RunStatus.RUNNING).transition(
        RunStatus.RETRIEVING
    ).transition(RunStatus.GENERATING).transition(
        RunStatus.VALIDATING
    ).transition(RunStatus.PASSED)
    script = ScriptVersion(
        id=new_id("script"), project_id=project.id, run_id=run.id,
        brief_version_id=brief.id, version=1, payload={}, evidence={}, created_at=utc_now(),
    )
    with repository._connect() as connection:
        connection.execute(
            """CREATE TRIGGER reject_pass BEFORE UPDATE OF status ON runs
               WHEN NEW.status = 'PASSED' BEGIN SELECT RAISE(ABORT, 'forced'); END"""
        )
    with pytest.raises(sqlite3.IntegrityError):
        repository.complete_run_with_script(passed, script)
    assert repository.get_script_for_run(run.id) is None
    persisted = repository.get_run(run.id)
    assert persisted is not None
    assert persisted.status is RunStatus.CLAIMED


def test_stuck_run_reconciler_requeues_once_then_uses_failed_job_store() -> None:
    repository = SQLiteCreatorRepository(":memory:")
    service = CreatorService(repository)
    project = service.create_project(title="租约协调", workspace_id="ws_test")
    brief = _brief(service, project.id)
    run, _ = service.create_run(
        workspace_id="ws_test", project_id=project.id, brief_version_id=brief.id,
        model_preference="本地演示", idempotency_key="reconcile-run",
    )
    assert repository.claim_run(run.id, "dead-worker", lease_seconds=-1)
    requeued, failed = repository.reconcile_expired_runs(max_attempts=3)
    assert requeued == [run.id]
    assert failed == []
    retrying = repository.get_run(run.id)
    assert retrying is not None
    assert retrying.status is RunStatus.RETRYING
    assert retrying.attempt == 2

    exhausted = replace(retrying, attempt=3)
    repository.save_run(exhausted)
    assert repository.claim_run(run.id, "dead-again", lease_seconds=-1)
    requeued, failed = repository.reconcile_expired_runs(max_attempts=3)
    assert requeued == []
    assert failed == [run.id]
    terminal = repository.get_run(run.id)
    assert terminal is not None
    assert terminal.status is RunStatus.FAILED
    with repository._connect() as connection:
        stored = connection.execute(
            "SELECT reason FROM failed_jobs WHERE run_id = ?", (run.id,)
        ).fetchone()
    assert stored["reason"] == "lease_exhausted"


def test_independent_verifier_rejects_delivery_mismatch() -> None:
    service = _service()
    project = service.create_project(title="验证专题", workspace_id="ws_test")
    brief = _brief(service, project.id)
    generated = generate_content_script(
        ContentBrief("中国剪纸", "剪刀落下", "初学者", "B站", "纪录片", duration="90秒", aspect_ratio="16:9")
    )
    broken = replace(
        generated,
        judgment=tuple(
            (label, "小红书" if label == "推荐平台" else value)
            for label, value in generated.judgment
        ),
    )
    result = verify_script(brief, broken)
    assert result.passed is False
    assert "platform_mismatch" in {issue.code for issue in result.issues}


def test_run_failure_is_persisted_without_fallback() -> None:
    service = _service()
    project = service.create_project(title="失败专题", workspace_id="ws_test")
    brief = _brief(service, project.id)
    run, _ = service.create_run(
        workspace_id="ws_test",
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="不存在的模型",
        idempotency_key="failure-run-001",
    )
    failed = service.execute_run(run.id)
    assert failed.status is RunStatus.FAILED
    assert failed.error_code == "ValueError"
    assert service.repository.get_script_for_run(run.id) is None


def test_failed_run_can_enter_a_bounded_retry_attempt() -> None:
    service = _service()
    project = service.create_project(title="重试专题", workspace_id="ws_test")
    brief = _brief(service, project.id)
    run, _ = service.create_run(
        workspace_id="ws_test",
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="不存在的模型",
        idempotency_key="retry-run-001",
    )
    first = service.execute_run(run.id)
    second = service.execute_run(run.id)
    third = service.execute_run(run.id)
    final = service.execute_run(run.id)
    assert first.attempt == 1
    assert second.attempt == 2
    assert third.attempt == 3
    assert final.attempt == 3
    assert final.status is RunStatus.FAILED


def test_sqlite_repository_migrates_legacy_run_schema(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    now = utc_now()
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, title TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE runs (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, brief_version_id TEXT NOT NULL,
                status TEXT NOT NULL, model_preference TEXT NOT NULL,
                idempotency_key TEXT NOT NULL, attempt INTEGER NOT NULL,
                error_code TEXT NOT NULL, error_message TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?)",
            ("prj_legacy", "ws_legacy", "旧项目", now, now),
        )
        connection.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run_legacy", "prj_legacy", "brief_legacy", "PENDING", "本地演示",
                "legacy-key", 0, "", "", now, now,
            ),
        )

    repository = SQLiteCreatorRepository(database)
    migrated = repository.get_run("run_legacy")

    assert migrated is not None
    assert migrated.workspace_id == "ws_legacy"
    assert migrated.request_fingerprint == ""

    reopened = SQLiteCreatorRepository(database)
    service = CreatorService(reopened)
    project = service.create_project(title="迁移后项目", workspace_id="ws_legacy")
    brief = _brief(service, project.id)
    created, is_new = service.create_run(
        workspace_id="ws_legacy",
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="本地演示",
        idempotency_key="post-migration-run",
    )

    assert is_new is True
    assert reopened.get_run(created.id) == created
