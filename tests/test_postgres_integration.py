from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from haha_auth.service import AuthService, InvalidRefreshTokenError
from haha_core.domain import RunStatus, ScriptVersion, new_id, utc_now
from haha_core.service import CreatorService
from haha_core.sqlalchemy_repository import SQLAlchemyCreatorRepository
from haha_identity.service import IdentityService
from haha_user_center.service import UserCenterService
from haha_workbench.service import WorkbenchService

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


def test_postgres_identity_roles_applications_and_context_are_durable(repository) -> None:
    repository.ensure_identity("identity-user", "pg-workspace", role="viewer")
    repository.ensure_identity("identity-reviewer", "pg-workspace", role="owner")
    service = IdentityService(repository)
    service.bootstrap("identity-user", "pg-workspace")
    service.activate_role("identity-user", "pg-workspace", "learner")
    service.switch_context("identity-user", "pg-workspace", "learner")
    application = service.apply_for_role(
        "identity-user", "pg-workspace", "seller", "PostgreSQL 身份申请集成测试"
    )
    service.decide_application(
        application.id, "identity-reviewer", "approved", "integration approved"
    )

    reloaded = IdentityService(SQLAlchemyCreatorRepository(POSTGRES_URL)).snapshot(
        "identity-user", "pg-workspace"
    )
    assert reloaded["profile"]["active_role"] == "learner"
    assert {item["role"] for item in reloaded["roles"] if item["status"] == "active"} == {
        "viewer",
        "buyer",
        "learner",
        "seller",
    }
    assert reloaded["applications"][0]["status"] == "approved"


def test_postgres_user_center_assets_preferences_and_history_are_durable(repository) -> None:
    repository.ensure_identity("center-user", "pg-workspace", role="viewer")
    service = UserCenterService(repository)
    service.bootstrap("center-user", "pg-workspace")
    service.update_profile(
        "center-user",
        "pg-workspace",
        display_name="文化探索者",
        bio="关注传统技艺",
        region="贵州",
        profile_visibility="members",
    )
    service.set_library_item(
        "center-user",
        "pg-workspace",
        kind_value="want_to_learn",
        target_id="content-1",
        title="苗绣",
        target_href="/content/content-1",
        active=True,
    )
    service.record_history(
        "center-user",
        "pg-workspace",
        content_id="content-1",
        title="苗绣",
        target_href="/content/content-1",
        progress_seconds=9,
        duration_seconds=10,
    )

    reloaded = UserCenterService(SQLAlchemyCreatorRepository(POSTGRES_URL)).snapshot(
        "center-user", "pg-workspace"
    )
    assert reloaded["account"]["display_name"] == "文化探索者"
    assert reloaded["account"]["region"] == "贵州"
    assert reloaded["summary"]["want_to_learn"] == 1
    assert reloaded["summary"]["history"] == 1
    assert reloaded["history"][0]["completed"] is True


def test_postgres_role_workbench_uses_durable_active_context(repository) -> None:
    creator = CreatorService(repository)
    repository.ensure_identity("workbench-user", "pg-workspace", role="owner")
    identity = IdentityService(repository)
    identity.bootstrap("workbench-user", "pg-workspace")
    identity.activate_role("workbench-user", "pg-workspace", "creator")
    identity.switch_context("workbench-user", "pg-workspace", "creator")
    creator.create_project(title="真实工作台项目", workspace_id="pg-workspace")

    reloaded = WorkbenchService(SQLAlchemyCreatorRepository(POSTGRES_URL)).snapshot(
        "workbench-user", "pg-workspace"
    )
    assert reloaded["role"] == "creator"
    assert reloaded["resources"][0]["title"] == "真实工作台项目"
    assert (
        next(item for item in reloaded["capabilities"] if item["key"] == "creator_projects")[
            "status"
        ]
        == "available"
    )


def test_postgres_parallel_identity_bootstrap_is_atomic(repository) -> None:
    def ensure() -> None:
        fresh_repository = SQLAlchemyCreatorRepository(POSTGRES_URL)
        fresh_repository.ensure_identity(
            "parallel-new-user", "parallel-new-workspace", role="owner"
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: ensure(), range(4)))

    assert repository.get_membership_role(
        "parallel-new-user", "parallel-new-workspace"
    ) == "owner"


def test_postgres_parallel_workbench_bootstrap_is_idempotent(repository) -> None:
    repository.ensure_identity("parallel-user", "pg-workspace", role="owner")

    def load_workbench() -> str:
        fresh_repository = SQLAlchemyCreatorRepository(POSTGRES_URL)
        return str(
            WorkbenchService(fresh_repository).snapshot("parallel-user", "pg-workspace")["role"]
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        roles = list(pool.map(lambda _: load_workbench(), range(4)))

    assert roles == ["viewer"] * 4
    grants = repository.list_role_grants("parallel-user", "pg-workspace")
    assert {item.role for item in grants if item.status == "active"} == {
        "viewer",
        "buyer",
    }


def test_postgres_refresh_rotation_is_atomic(repository) -> None:
    auth = AuthService(repository)
    auth.bootstrap_account(
        user_id="pg-auth-user",
        workspace_id="pg-auth-workspace",
        email="pg-auth@haha.local",
        password="Postgres-Auth-Test-Password-2026",
        role="viewer",
    )
    initial = auth.login(
        email="pg-auth@haha.local",
        password="Postgres-Auth-Test-Password-2026",
        workspace_id="pg-auth-workspace",
    )

    def refresh_once() -> str:
        try:
            AuthService(SQLAlchemyCreatorRepository(POSTGRES_URL)).refresh(
                str(initial["refresh_token"])
            )
        except InvalidRefreshTokenError:
            return "rejected"
        return "rotated"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: refresh_once(), range(2)))
    assert sorted(outcomes) == ["rejected", "rotated"]


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
    passed = (
        claimed.transition(RunStatus.RUNNING)
        .transition(RunStatus.RETRIEVING)
        .transition(RunStatus.GENERATING)
        .transition(RunStatus.VALIDATING)
        .transition(RunStatus.PASSED)
    )
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


def test_postgres_failed_job_operations_are_scoped_and_atomic(repository) -> None:
    service, project, brief = _prepared_service(repository)
    run, _ = service.create_run(
        workspace_id="pg-workspace",
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="不存在的模型",
        idempotency_key="postgres-failed-job-operations",
    )
    failed = service.execute_run(run.id)
    repository.record_failed_job(failed.id, failed.error_code)
    job = repository.list_failed_jobs("pg-workspace")[0]

    assert repository.list_failed_jobs("another-workspace") == []

    def retry_once():
        return repository.retry_failed_job(
            job.id, "pg-workspace", max_attempts=service.max_run_attempts
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        attempts = list(executor.map(lambda _: retry_once(), range(2)))
    successful = [attempt for attempt in attempts if attempt is not None]
    assert len(successful) == 1
    retrying = successful[0]
    assert retrying.status is RunStatus.RETRYING
    assert retrying.attempt == 2
    resolved = repository.get_failed_job(job.id, "pg-workspace")
    assert resolved is not None
    assert resolved.resolved_at
