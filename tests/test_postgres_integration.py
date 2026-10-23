from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from haha_auth.service import (
    AccountRegistrationError,
    AuthService,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from haha_commerce.domain import CommerceConflictError, ShoppingAdvisorInteraction
from haha_commerce.service import CommerceService
from haha_commerce.sqlalchemy_repository import SQLAlchemyCommerceRepository
from haha_community.domain import CommunityConflictError
from haha_community.media_storage import FileSystemMediaStorage
from haha_community.service import CommunityService
from haha_community.sqlalchemy_repository import SQLAlchemyCommunityRepository
from haha_core.database_safety import assert_test_database_reset_safe
from haha_core.domain import RunStatus, ScriptVersion, new_id, utc_now
from haha_core.repository import RepositoryConflictError
from haha_core.service import CreatorService
from haha_core.sqlalchemy_repository import SQLAlchemyCreatorRepository
from haha_identity.domain import RoleGrant
from haha_identity.service import IdentityService
from haha_learning.seed import LESSON_UNIT_ID, PATH_ID, QUIZ_ID, QUIZ_UNIT_ID
from haha_learning.service import LearningService
from haha_learning.tutor import HeritageTutor
from haha_media.model_router import CallEvidence, TextModelResult
from haha_user_center.service import UserCenterService
from haha_workbench.service import WorkbenchService

POSTGRES_URL = os.getenv("HAHA_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="HAHA_TEST_POSTGRES_URL not configured")


@pytest.fixture()
def repository() -> SQLAlchemyCreatorRepository:
    assert_test_database_reset_safe(POSTGRES_URL)
    repo = SQLAlchemyCreatorRepository(POSTGRES_URL)
    with repo.engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE creator_image_assets, image_generation_requests, script_revisions, "
                "script_versions, runs, brief_versions, projects, "
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


def test_postgres_script_revision_is_durable_and_concurrent_safe(repository) -> None:
    service, project, brief = _prepared_service(repository)
    run, _ = service.create_run(
        workspace_id="pg-workspace", project_id=project.id,
        brief_version_id=brief.id, model_preference="本地演示",
        idempotency_key="postgres-script-revision",
    )
    assert service.execute_run(run.id).status is RunStatus.PASSED
    generated = repository.get_script_for_run(run.id)
    assert generated is not None
    payload = {
        key: generated.payload[key]
        for key in ("title", "hook", "voiceover", "shots", "caption", "tags")
    }

    def revise():
        try:
            return service.create_script_revision(
                run.id, payload=payload, expected_version=0, user_id="pg-user"
            )
        except Exception as exc:
            return exc

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: revise(), range(4)))
    winners = [item for item in results if not isinstance(item, Exception)]
    assert len(winners) == 1
    restored = SQLAlchemyCreatorRepository(POSTGRES_URL).get_latest_script_revision(run.id)
    assert restored is not None
    assert restored.id == winners[0].id
    assert restored.version == 1


def test_postgres_image_run_request_is_atomic_and_idempotent(repository) -> None:
    service, project, brief = _prepared_service(repository)
    source, _ = service.create_run(
        workspace_id="pg-workspace", project_id=project.id, brief_version_id=brief.id,
        model_preference="本地演示", idempotency_key="postgres-image-source",
    )
    assert service.execute_run(source.id).status is RunStatus.PASSED
    generated = repository.get_script_for_run(source.id)
    assert generated is not None
    revision = service.create_script_revision(
        source.id,
        payload={key: generated.payload[key] for key in ("title", "hook", "voiceover", "shots", "caption", "tags")},
        expected_version=0, user_id="pg-user",
    )
    service.review_script_revision(
        source.id, expected_version=revision.version, note="reviewed", user_id="pg-user"
    )

    def submit():
        return service.create_image_run(
            workspace_id="pg-workspace", source_run_id=source.id, prompt="剪纸纹样特写",
            negative_prompt="文字", size="1K", count=1, watermark=True,
            reference_asset_ids=(), idempotency_key="postgres-image-run", user_id="pg-user",
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: submit(), range(4)))
    assert len({run.id for run, _ in results}) == 1
    assert sum(1 for _, created in results if created) == 1
    run_id = results[0][0].id
    restored = SQLAlchemyCreatorRepository(POSTGRES_URL).get_image_request(run_id)
    assert restored is not None
    assert restored.prompt == "剪纸纹样特写"


def test_postgres_identity_roles_applications_and_context_are_durable(repository) -> None:
    repository.ensure_identity("identity-user", "pg-workspace", role="viewer")
    repository.ensure_identity("identity-reviewer", "pg-workspace", role="owner")
    service = IdentityService(repository)
    service.bootstrap("identity-user", "pg-workspace")
    service.activate_role("identity-user", "pg-workspace", "creator")
    service.switch_context("identity-user", "pg-workspace", "creator")
    application = service.apply_for_role(
        "identity-user", "pg-workspace", "seller", "PostgreSQL 身份申请集成测试"
    )
    service.decide_application(
        application.id, "identity-reviewer", "approved", "integration approved"
    )

    reloaded = IdentityService(SQLAlchemyCreatorRepository(POSTGRES_URL)).snapshot(
        "identity-user", "pg-workspace"
    )
    assert reloaded["profile"]["active_role"] == "creator"
    assert {item["role"] for item in reloaded["roles"] if item["status"] == "active"} == {
        "viewer",
        "buyer",
        "learner",
        "creator",
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


def test_postgres_learning_loop_is_durable_server_graded_and_idempotent(
    repository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    repository.ensure_identity("learning-user", "pg-workspace", role="owner")
    identity = IdentityService(repository)
    identity.bootstrap("learning-user", "pg-workspace")
    service = LearningService(repository)
    initial = service.bootstrap("learning-user", "pg-workspace")
    assert initial["ai_tutor"]["status"] == "blocked"

    service.enroll_path(
        "learning-user", "pg-workspace", PATH_ID,
        source_content_id="", idempotency_key="pg-learning-enroll-01",
    )

    def complete_same_unit() -> dict[str, object]:
        return LearningService(SQLAlchemyCreatorRepository(POSTGRES_URL)).complete_unit(
            "learning-user", "pg-workspace", LESSON_UNIT_ID,
            expected_version=0, idempotency_key="pg-learning-unit-0001",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: complete_same_unit(), range(2)))
    assert all(item["summary"]["completed_units"] == 1 for item in results)

    quiz_unit = next(
        unit
        for path in results[0]["paths"]
        for unit in path["units"]
        if unit["id"] == QUIZ_UNIT_ID
    )
    answers = {question["id"]: 1 for question in quiz_unit["quiz"]["questions"]}
    result = service.submit_quiz(
        "learning-user", "pg-workspace", QUIZ_ID,
        answers=answers, expected_progress_version=0,
        idempotency_key="pg-learning-quiz-0001",
    )
    assert result["last_quiz_result"]["passed"] is True

    restored = LearningService(SQLAlchemyCreatorRepository(POSTGRES_URL)).bootstrap(
        "learning-user", "pg-workspace"
    )
    assert restored["paths"][0]["completion_percent"] == 100
    assert restored["summary"]["quiz_attempts"] == 1
    assert restored["summary"]["achievements"] == 2


def test_postgres_community_state_is_durable_and_submission_lock_is_atomic(
    repository,
) -> None:
    with repository.engine.begin() as connection:
        connection.execute(text(
            "TRUNCATE community_import_receipts, community_submission_events, "
            "community_submission_revisions, community_submissions, "
            "community_annotations, community_comments, community_respects, "
            "community_entities CASCADE"
        ))
    repository.ensure_identity("community-user", "pg-workspace", role="owner")
    community_repository = SQLAlchemyCommunityRepository(POSTGRES_URL)
    service = CommunityService(
        community_repository,
        UserCenterService(repository),
    )
    snapshot = service.bootstrap("community-user", "pg-workspace")
    content_id = str(snapshot["contents"][0]["id"])
    service.set_reaction(
        "community-user", "pg-workspace", content_id, "bookmark", True
    )
    comment = service.create_comment(
        "community-user",
        "pg-workspace",
        "PostgreSQL 用户",
        content_id,
        "持久评论",
    )
    draft = service.create_submission(
        "community-user", "pg-workspace", "creator", "article", "并发版本"
    )

    def update_once(title: str) -> str:
        fresh = CommunityService(
            SQLAlchemyCommunityRepository(POSTGRES_URL),
            UserCenterService(SQLAlchemyCreatorRepository(POSTGRES_URL)),
        )
        try:
            fresh.update_submission(
                "community-user",
                "pg-workspace",
                "creator",
                str(draft["id"]),
                1,
                {"title": title},
            )
        except CommunityConflictError:
            return "conflict"
        return "updated"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(update_once, ("版本 A", "版本 B")))

    restored = CommunityService(
        SQLAlchemyCommunityRepository(POSTGRES_URL),
        UserCenterService(SQLAlchemyCreatorRepository(POSTGRES_URL)),
    ).bootstrap("community-user", "pg-workspace")
    restored_content = next(
        item for item in restored["contents"] if item["id"] == content_id
    )
    assert "bookmark" in restored_content["viewer"]["reactions"]
    assert any(item["id"] == comment["id"] for item in restored["comments"])
    assert sorted(outcomes) == ["conflict", "updated"]
    assert restored["drafts"][0]["version"] == 2


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
        "learner",
    }
    notifications = repository.list_user_notifications("parallel-user", "pg-workspace")
    assert len(notifications) == 1
    assert notifications[0].title == "文化账户已启用"


def test_postgres_commerce_advisor_insert_and_update_are_observable(repository) -> None:
    workspace_id = "commerce-advisor-pg-workspace"
    user_id = "commerce-advisor-pg-user"
    repository.ensure_identity(user_id, workspace_id, role="owner")
    IdentityService(repository).bootstrap(user_id, workspace_id)
    commerce_repository = SQLAlchemyCommerceRepository(POSTGRES_URL)
    now = "2026-10-20T00:00:00.000+00:00"
    pending = ShoppingAdvisorInteraction(
        id="advisor-pg-001",
        user_id=user_id,
        workspace_id=workspace_id,
        question="想找一件日常礼物",
        answer="",
        recommendations_json="[]",
        suggestions_json="[]",
        status="pending",
        mode="pending",
        model="deepseek-flash",
        provider="",
        request_id="",
        input_tokens=0,
        output_tokens=0,
        error_code="",
        idempotency_key="advisor-pg-idempotency-001",
        request_hash="a" * 64,
        created_at=now,
        updated_at=now,
    )
    assert commerce_repository.create_advisor_interaction(pending) is True
    assert commerce_repository.create_advisor_interaction(pending) is False
    completed = replace(
        pending,
        answer="当前目录没有可售商品。",
        status="completed",
        mode="no_catalog",
    )
    assert commerce_repository.update_advisor_interaction(completed, "pending") is True
    restored = commerce_repository.find_advisor_interaction(
        user_id, workspace_id, pending.idempotency_key
    )
    assert restored is not None
    assert restored.status == "completed"


def test_postgres_commerce_checkout_serializes_inventory(repository) -> None:
    workspace_id = "commerce-pg-workspace"
    seller_id = "commerce-pg-seller"
    reviewer_id = "commerce-pg-reviewer"
    buyers = ("commerce-pg-buyer-a", "commerce-pg-buyer-b")
    identity = IdentityService(repository)
    for user_id in (seller_id, reviewer_id, *buyers):
        repository.ensure_identity(user_id, workspace_id, role="owner")
        identity.bootstrap(user_id, workspace_id)
    now = utc_now()
    for user_id, role in ((seller_id, "seller"), (reviewer_id, "reviewer")):
        repository.save_role_grant(RoleGrant(
            id=new_id("grant"), user_id=user_id, workspace_id=workspace_id,
            role=role, status="active", scope_json="{}", granted_by="pg-test",
            created_at=now, revoked_at="",
        ))

    commerce_repository = SQLAlchemyCommerceRepository(POSTGRES_URL)
    commerce = CommerceService(commerce_repository, repository)
    commerce.open_store(seller_id, workspace_id, "PostgreSQL 沙盒店铺")
    created = commerce.create_product(
        seller_id, workspace_id,
        title="PostgreSQL 库存并发样品",
        summary="只用于验证库存事务，不代表正式商品。",
        price_cents=100,
        source_note="内部测试，来源与授权未核验。",
        idempotency_key="pg-product-create-0001",
    )
    product = created["seller_products"][0]
    submitted = commerce.submit_product(
        seller_id, workspace_id, product["id"], product["version"]
    )
    queued = submitted["seller_products"][0]
    commerce.moderate_product(
        reviewer_id, workspace_id, product["id"], "approved",
        "仅用于 PostgreSQL 集成测试。", queued["version"],
    )
    commerce.set_inventory(seller_id, workspace_id, product["id"], 1, 0)
    for buyer_id in buyers:
        commerce.set_cart_item(buyer_id, workspace_id, product["id"], 1, 0)

    def checkout(buyer_id: str) -> str:
        try:
            CommerceService(
                SQLAlchemyCommerceRepository(POSTGRES_URL),
                SQLAlchemyCreatorRepository(POSTGRES_URL),
            ).checkout(buyer_id, workspace_id, f"pg-checkout-{buyer_id}")
        except CommerceConflictError:
            return "inventory_conflict"
        return "created"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(checkout, buyers))

    assert sorted(outcomes) == ["created", "inventory_conflict"]
    inventory = commerce_repository.get_inventory(product["id"], workspace_id)
    assert inventory is not None
    assert inventory.available_qty == 0
    assert sum(
        len(commerce_repository.list_orders(workspace_id, buyer_user_id=buyer_id))
        for buyer_id in buyers
    ) == 1


def test_postgres_commerce_concurrent_idempotency_replays_winner(repository) -> None:
    workspace_id = "commerce-idempotency-workspace"
    seller_id = "commerce-idempotency-seller"
    reviewer_id = "commerce-idempotency-reviewer"
    buyer_id = "commerce-idempotency-buyer"
    identity = IdentityService(repository)
    for user_id in (seller_id, reviewer_id, buyer_id):
        repository.ensure_identity(user_id, workspace_id, role="owner")
        identity.bootstrap(user_id, workspace_id)
    now = utc_now()
    for user_id, role in ((seller_id, "seller"), (reviewer_id, "reviewer")):
        repository.save_role_grant(RoleGrant(
            id=new_id("grant"), user_id=user_id, workspace_id=workspace_id,
            role=role, status="active", scope_json="{}", granted_by="pg-test",
            created_at=now, revoked_at="",
        ))

    commerce_repository = SQLAlchemyCommerceRepository(POSTGRES_URL)
    commerce = CommerceService(commerce_repository, repository)
    commerce.open_store(seller_id, workspace_id, "并发幂等沙盒店铺")
    product = commerce.create_product(
        seller_id,
        workspace_id,
        title="并发幂等测试作品",
        summary="只验证事务重放，不代表正式商品。",
        price_cents=200,
        source_note="内部测试，来源与授权未核验。",
        idempotency_key="pg-idempotent-product-0001",
    )["seller_products"][0]
    queued = commerce.submit_product(
        seller_id, workspace_id, product["id"], product["version"]
    )["seller_products"][0]
    commerce.moderate_product(
        reviewer_id,
        workspace_id,
        product["id"],
        "approved",
        "仅用于 PostgreSQL 并发幂等测试。",
        queued["version"],
    )
    commerce.set_inventory(seller_id, workspace_id, product["id"], 2, 0)
    commerce.set_cart_item(buyer_id, workspace_id, product["id"], 1, 0)

    checkout_key = "pg-concurrent-checkout-same-key"

    def checkout_same_key() -> str:
        snapshot = CommerceService(
            SQLAlchemyCommerceRepository(POSTGRES_URL),
            SQLAlchemyCreatorRepository(POSTGRES_URL),
        ).checkout(buyer_id, workspace_id, checkout_key)
        return next(
            item["id"]
            for item in snapshot["buyer_orders"]
            if item["checkout_key"] == checkout_key
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        order_ids = list(pool.map(lambda _: checkout_same_key(), range(4)))
    assert len(set(order_ids)) == 1
    order_id = order_ids[0]
    orders = commerce_repository.list_orders(workspace_id, buyer_user_id=buyer_id)
    assert [item.id for item in orders if item.checkout_key == checkout_key] == [order_id]

    payment_key = "pg-concurrent-payment-same-key"

    def pay_same_key() -> str:
        snapshot = CommerceService(
            SQLAlchemyCommerceRepository(POSTGRES_URL),
            SQLAlchemyCreatorRepository(POSTGRES_URL),
        ).sandbox_pay(buyer_id, workspace_id, order_id, 1, payment_key)
        return next(item for item in snapshot["buyer_orders"] if item["id"] == order_id)[
            "payment"
        ]["id"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        payment_ids = list(pool.map(lambda _: pay_same_key(), range(4)))
    assert len(set(payment_ids)) == 1
    payment = commerce_repository.get_payment(order_id, workspace_id)
    assert payment is not None
    assert payment.id == payment_ids[0]


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


def test_postgres_password_change_and_session_revocation_are_atomic(repository) -> None:
    auth = AuthService(repository)
    auth.bootstrap_account(
        user_id="pg-password-user",
        workspace_id="pg-password-workspace",
        email="pg-password@haha.local",
        password="Postgres-Original-Password-2026",
        role="owner",
    )
    first = auth.login(
        email="pg-password@haha.local",
        password="Postgres-Original-Password-2026",
    )
    second = auth.login(
        email="pg-password@haha.local",
        password="Postgres-Original-Password-2026",
    )
    revoked = auth.change_password(
        user_id="pg-password-user",
        workspace_id="pg-password-workspace",
        current_password="Postgres-Original-Password-2026",
        new_password="Postgres-Replacement-Password-2026",
    )
    assert revoked == 2
    with pytest.raises(InvalidRefreshTokenError):
        auth.refresh(str(first["refresh_token"]))
    with pytest.raises(InvalidRefreshTokenError):
        auth.refresh(str(second["refresh_token"]))
    with pytest.raises(InvalidCredentialsError):
        auth.login(
            email="pg-password@haha.local",
            password="Postgres-Original-Password-2026",
        )
    assert auth.login(
        email="pg-password@haha.local",
        password="Postgres-Replacement-Password-2026",
    )["account"]["user_id"] == "pg-password-user"


def test_postgres_public_registration_is_transactional_unique_and_restorable(
    repository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HAHA_SELF_REGISTRATION_ENABLED", "true")
    email = "pg-public-registration@haha.local"
    password = "Postgres-Registration-Password-2026"

    def register_once() -> str:
        try:
            result = AuthService(
                SQLAlchemyCreatorRepository(POSTGRES_URL)
            ).register(email=email, password=password, display_name="PostgreSQL 新成员")
        except AccountRegistrationError:
            return "duplicate"
        return str(result["account"]["workspace_id"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: register_once(), range(2)))

    created = [item for item in outcomes if item != "duplicate"]
    assert len(created) == 1
    assert outcomes.count("duplicate") == 1
    restored = AuthService(SQLAlchemyCreatorRepository(POSTGRES_URL)).login(
        email=email, password=password
    )
    assert restored["account"]["workspace_id"] == created[0]
    assert restored["account"]["role"] == "owner"
    profile = SQLAlchemyCreatorRepository(POSTGRES_URL).ensure_user_profile(
        str(restored["account"]["user_id"]), created[0]
    )
    assert profile.display_name == "PostgreSQL 新成员"


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
    assert reclaimed.claim_epoch == claimed.claim_epoch + 1
    assert reclaimed.lock_version > claimed.lock_version
    with pytest.raises(RepositoryConflictError):
        repository.save_claimed_run(
            claimed.transition(RunStatus.RUNNING),
            claimed.claimed_by,
            claimed.claim_epoch,
        )


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
        repository.complete_run_with_script(
            passed, script, "worker-a", claimed.claim_epoch
        )
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


class _PostgresTutorRouter:
    def __init__(self) -> None:
        self.calls = 0

    def status(self):
        return SimpleNamespace(text_ready=True, text_model="deepseek-flash")

    def generate_json(self, task: str, **kwargs) -> TextModelResult:
        self.calls += 1
        return TextModelResult(
            data={
                "answer": "中国剪纸以剪刻和纹样设计为核心 [F-096]。",
                "used_source_ids": ["F-096"],
                "uncertainty": "仅依据当前版本化目录。",
                "suggested_questions": [],
            },
            evidence=CallEvidence(
                provider="deepseek",
                model="deepseek-flash",
                request_id="pg-tutor-request",
                latency_ms=100,
                input_tokens=300,
                output_tokens=60,
            ),
        )


def test_postgres_learning_tutor_is_durable_and_idempotent(repository) -> None:
    repository.ensure_identity("pg-tutor-user", "pg-workspace", role="owner")
    identity = IdentityService(repository)
    identity.bootstrap("pg-tutor-user", "pg-workspace")
    router = _PostgresTutorRouter()
    tutor = HeritageTutor(router)
    service = LearningService(repository, tutor)

    answered = service.ask_tutor(
        "pg-tutor-user",
        "pg-workspace",
        question="中国剪纸有哪些特点？",
        idempotency_key="pg-tutor-question-001",
    )
    assert answered["last_tutor_result"]["request_id"] == "pg-tutor-request"

    reloaded = LearningService(SQLAlchemyCreatorRepository(POSTGRES_URL), tutor)
    restored = reloaded.bootstrap("pg-tutor-user", "pg-workspace")
    assert restored["tutor_history"][0]["citations"][0]["source_id"] == "F-096"
    replayed = reloaded.ask_tutor(
        "pg-tutor-user",
        "pg-workspace",
        question="中国剪纸有哪些特点？",
        idempotency_key="pg-tutor-question-001",
    )
    assert replayed["last_tutor_result"]["id"] == answered["last_tutor_result"]["id"]
    assert router.calls == 1


def test_postgres_learning_contribution_retry_is_concurrent_and_isolated(repository) -> None:
    repository.ensure_identity("pg-contributor", "pg-learning-governance", role="owner")
    IdentityService(repository).bootstrap("pg-contributor", "pg-learning-governance")

    def submit() -> str:
        service = LearningService(SQLAlchemyCreatorRepository(POSTGRES_URL))
        snapshot = service.submit_knowledge_contribution(
            "pg-contributor", "pg-learning-governance",
            topic="并发待核验贡献", body="重复提交只能形成一条隔离审核记录。",
            source_title="来源", source_url="https://example.com/reference",
            source_version="v1", idempotency_key="pg-s08-contribution-001",
        )
        return snapshot["knowledge_contributions"][0]["id"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        contribution_ids = list(pool.map(lambda _: submit(), range(4)))
    assert len(set(contribution_ids)) == 1
    restored = LearningService(SQLAlchemyCreatorRepository(POSTGRES_URL)).bootstrap(
        "pg-contributor", "pg-learning-governance"
    )
    assert len(restored["knowledge_contributions"]) == 1
    assert restored["knowledge_contributions"][0]["status"] == "submitted"


def test_postgres_commerce_product_edit_and_media_are_durable(repository) -> None:
    repository.ensure_identity("pg-media-seller", "pg-media-workspace", role="owner")
    identity = IdentityService(repository)
    identity.bootstrap("pg-media-seller", "pg-media-workspace")
    repository.save_role_grant(RoleGrant(
        id="pg-media-seller-grant", user_id="pg-media-seller",
        workspace_id="pg-media-workspace", role="seller", status="active",
        scope_json='{"workspace_id":"pg-media-workspace"}', granted_by="pg-test",
        created_at=utc_now(), revoked_at="",
    ))
    commerce_repository = SQLAlchemyCommerceRepository(POSTGRES_URL)
    storage = FileSystemMediaStorage(Path(".test-artifacts") / "postgres-commerce-media")
    commerce = CommerceService(commerce_repository, repository, media_storage=storage)
    commerce.open_store("pg-media-seller", "pg-media-workspace", "PostgreSQL 图片店铺")
    created = commerce.create_product(
        "pg-media-seller", "pg-media-workspace", title="原始商品",
        summary="PostgreSQL 商品编辑与图片测试。", price_cents=8800,
        source_note="测试卖家声明来源。", idempotency_key="pg-product-media-create-001",
    )
    product = created["seller_products"][0]
    updated = commerce.update_product_details(
        "pg-media-seller", "pg-media-workspace", product["id"],
        title="已编辑商品", summary="编辑结果应持久化。", price_cents=9900,
        source_note="更新后的测试来源说明。", category_slug="other",
        craft_type="测试工艺", origin_region="测试地区", season_tag="秋季",
        expected_version=product["version"],
    )
    product = updated["seller_products"][0]
    staged = storage.create_staging_path()
    staged.write_bytes(b"\x89PNG\r\n\x1a\npostgres-image")
    uploaded = commerce.add_product_image(
        "pg-media-seller", "pg-media-workspace", product["id"],
        staged_path=staged, filename="postgres.png", declared_content_type="image/png",
        alt_text="PostgreSQL 测试图片", source_note="测试生成，不作为正式商品素材。",
        expected_version=product["version"],
    )
    media_id = uploaded["seller_products"][0]["media"][0]["id"]
    reloaded = CommerceService(
        SQLAlchemyCommerceRepository(POSTGRES_URL), repository, media_storage=storage
    ).snapshot("pg-media-seller", "pg-media-workspace")
    assert reloaded["seller_products"][0]["title"] == "已编辑商品"
    assert reloaded["seller_products"][0]["price_cents"] == 9900
    assert reloaded["seller_products"][0]["media"][0]["id"] == media_id
