from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from haha_core.domain import RunStatus, ScriptVersion, new_id, utc_now
from haha_core.service import CreatorService
from haha_core.sqlalchemy_repository import SQLAlchemyCreatorRepository

POSTGRES_URL = os.getenv("HAHA_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="HAHA_TEST_POSTGRES_URL not configured")


@pytest.fixture()
def repository() -> SQLAlchemyCreatorRepository:
    repo = SQLAlchemyCreatorRepository(POSTGRES_URL)
    with repo.engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE script_versions, runs, brief_versions, projects, "
                "memberships, users, workspaces CASCADE"
            )
        )
    return repo


def _prepared_service(repository: SQLAlchemyCreatorRepository):
    service = CreatorService(repository)
    repository.ensure_identity("pg-user", "pg-workspace", role="owner")
    project = service.create_project(title="PostgreSQL 集成", workspace_id="pg-workspace")
    brief = service.create_brief(
        project.id,
        craft="中国剪纸",
        story_seed="剪刀形成纹样",
        audience="文化初学者",
        platform="B站",
        tone="人物纪实",
        goal="文化科普",
        duration="90秒",
        aspect_ratio="16:9",
        asset_context="PostgreSQL integration",
    )
    return service, project, brief


def test_postgres_membership_and_concurrent_idempotency(repository) -> None:
    service, project, brief = _prepared_service(repository)
    assert repository.get_membership_role("pg-user", "pg-workspace") == "owner"

    def submit():
        return service.create_run(
            workspace_id="pg-workspace",
            project_id=project.id,
            brief_version_id=brief.id,
            model_preference="本地演示",
            idempotency_key="postgres-concurrent-key",
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: submit(), range(4)))
    assert len({run.id for run, _ in results}) == 1
    assert sum(1 for _, created in results if created) == 1


def test_postgres_worker_claim_and_expired_lease(repository) -> None:
    service, project, brief = _prepared_service(repository)
    run, _ = service.create_run(
        workspace_id="pg-workspace",
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="本地演示",
        idempotency_key="postgres-claim",
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(
            pool.map(
                lambda worker: repository.claim_run(run.id, worker),
                ("worker-a", "worker-b"),
            )
        )
    assert sum(claim is not None for claim in claims) == 1

    claimed = next(claim for claim in claims if claim is not None)
    with repository.engine.begin() as connection:
        connection.execute(
            text("UPDATE runs SET lease_until = '2000-01-01T00:00:00+00:00' WHERE id = :id"),
            {"id": run.id},
        )
    reclaimed = repository.claim_run(run.id, "worker-c")
    assert reclaimed is not None
    assert reclaimed.status is RunStatus.CLAIMED
    assert reclaimed.claimed_by == "worker-c"
    assert reclaimed.lock_version > claimed.lock_version


def test_postgres_cancel_is_atomic_and_blocks_stale_worker_write(repository) -> None:
    service, project, brief = _prepared_service(repository)
    run, _ = service.create_run(
        workspace_id="pg-workspace",
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="本地演示",
        idempotency_key="postgres-cancel",
    )
    claimed = repository.claim_run(run.id, "worker-before-cancel")
    assert claimed is not None

    cancelled = service.cancel_run(run.id)
    assert cancelled.status is RunStatus.CANCELLED
    repository.save_run(claimed.transition(RunStatus.RUNNING))
    persisted = repository.get_run(run.id)
    assert persisted is not None
    assert persisted.status is RunStatus.CANCELLED


def test_postgres_completion_failure_rolls_back_script_and_run(repository) -> None:
    service, project, brief = _prepared_service(repository)
    run, _ = service.create_run(
        workspace_id="pg-workspace",
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="本地演示",
        idempotency_key="postgres-rollback",
    )
    claimed = repository.claim_run(run.id, "worker-a")
    assert claimed is not None
    passed = claimed.transition(RunStatus.RUNNING).transition(
        RunStatus.RETRIEVING
    ).transition(RunStatus.GENERATING).transition(
        RunStatus.VALIDATING
    ).transition(RunStatus.PASSED)
    script = ScriptVersion(
        id=new_id("script"),
        project_id=project.id,
        run_id=run.id,
        brief_version_id=brief.id,
        version=1,
        payload={},
        evidence={},
        created_at=utc_now(),
    )
    with repository.engine.begin() as connection:
        connection.execute(
            text(
                """CREATE OR REPLACE FUNCTION reject_pass() RETURNS trigger AS $$
                BEGIN
                    IF NEW.status = 'PASSED' THEN RAISE EXCEPTION 'forced rollback'; END IF;
                    RETURN NEW;
                END; $$ LANGUAGE plpgsql"""
            )
        )
        connection.execute(
            text(
                "CREATE TRIGGER reject_pass_trigger BEFORE UPDATE ON runs "
                "FOR EACH ROW EXECUTE FUNCTION reject_pass()"
            )
        )
    with pytest.raises(DBAPIError):
        repository.complete_run_with_script(passed, script)
    assert repository.get_script_for_run(run.id) is None
    persisted = repository.get_run(run.id)
    assert persisted is not None
    assert persisted.status is RunStatus.CLAIMED
    with repository.engine.begin() as connection:
        connection.execute(text("DROP TRIGGER reject_pass_trigger ON runs"))
        connection.execute(text("DROP FUNCTION reject_pass()"))


def test_postgres_reconciler_is_bounded_and_persists_exhaustion(repository) -> None:
    service, project, brief = _prepared_service(repository)
    run, _ = service.create_run(
        workspace_id="pg-workspace",
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="本地演示",
        idempotency_key="postgres-reconcile",
    )
    assert repository.claim_run(run.id, "dead-worker", lease_seconds=-1)
    requeued, failed = repository.reconcile_expired_runs(max_attempts=3)
    assert requeued == [run.id]
    assert failed == []
    retrying = repository.get_run(run.id)
    assert retrying is not None
    repository.save_run(replace(retrying, attempt=3))
    assert repository.claim_run(run.id, "dead-again", lease_seconds=-1)
    requeued, failed = repository.reconcile_expired_runs(max_attempts=3)
    assert requeued == []
    assert failed == [run.id]
    with repository.engine.connect() as connection:
        reason = connection.scalar(
            text("SELECT reason FROM failed_jobs WHERE run_id = :run_id"),
            {"run_id": run.id},
        )
    assert reason == "lease_exhausted"
