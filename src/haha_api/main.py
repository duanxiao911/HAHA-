"""FastAPI entry point. Business behavior remains in the framework-free core."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import asdict
from urllib.parse import unquote
from uuid import uuid4

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from redis import Redis

from haha_api.auth import (
    Principal,
    Role,
    authenticate,
    authorize_metrics,
    require_project_access,
    require_write_access,
    validate_security_configuration,
)
from haha_api.observability import log_event, metrics, request_id_context
from haha_auth.service import (
    AccountLockedError,
    AccountRegistrationError,
    AuthService,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RegistrationDisabledError,
)
from haha_commerce.advisor import ShoppingAdvisor
from haha_commerce.bootstrap import build_commerce_repository
from haha_commerce.domain import (
    CommerceAdvisorRateLimitError,
    CommerceAdvisorUnavailableError,
    CommerceConflictError,
    CommerceNotFoundError,
    CommercePermissionError,
)
from haha_commerce.repository import CommerceRepository
from haha_commerce.service import CommerceService
from haha_community.bootstrap import build_community_repository
from haha_community.domain import (
    CommunityConflictError,
    CommunityNotFoundError,
    CommunityPermissionError,
    CommunityValidationError,
)
from haha_community.media_storage import FileSystemMediaStorage
from haha_community.repository import CommunityRepository
from haha_community.service import CommunityService
from haha_core.bootstrap import build_repository, enqueue_run
from haha_core.domain import TERMINAL_RUN_STATUSES
from haha_core.repository import CreatorRepository
from haha_core.service import (
    CreatorService,
    FailedJobNotRetryableError,
    IdempotencyConflictError,
    RunNotCancellableError,
    ScriptRevisionConflictError,
)
from haha_identity.service import (
    IdentityConflictError,
    IdentityNotFoundError,
    IdentityPermissionError,
    IdentityService,
)
from haha_learning.domain import (
    LearningConflictError,
    LearningNotFoundError,
    LearningPermissionError,
    LearningTutorRateLimitError,
    LearningTutorUnavailableError,
)
from haha_learning.service import LearningService
from haha_learning.tutor import HeritageTutor
from haha_media.model_router import get_model_router
from haha_user_center.service import UserCenterNotFoundError, UserCenterService
from haha_workbench.service import WorkbenchPermissionError, WorkbenchService

REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def normalize_request_id(value: str) -> str:
    candidate = value.strip()
    return candidate if REQUEST_ID.fullmatch(candidate) else uuid4().hex


def apply_security_headers(response: Response) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    if os.getenv("HAHA_ENVIRONMENT", "production").lower() in {
        "staging",
        "production",
    }:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)


class BriefCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    craft: str = Field(min_length=1, max_length=200)
    story_seed: str = Field(default="", max_length=4000)
    audience: str = Field(min_length=1, max_length=200)
    platform: str = Field(min_length=1, max_length=50)
    tone: str = Field(min_length=1, max_length=100)
    goal: str = Field(default="文化科普", max_length=200)
    duration: str = Field(min_length=1, max_length=20)
    aspect_ratio: str = Field(min_length=1, max_length=20)
    asset_context: str = Field(default="", max_length=24000)


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brief_version_id: str
    model_preference: str = Field(
        default="本地演示",
        pattern="^(DeepSeek-V4\\.1-Flash|DeepSeek-V4-Pro|本地演示)$",
    )


class ScriptRevisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict[str, object]
    expected_version: int = Field(ge=0)


class ScriptRevisionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    note: str = Field(default="", max_length=2000)


class RoleApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(min_length=3, max_length=32)
    reason: str = Field(min_length=8, max_length=1000)


class IdentityContextSwitch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(min_length=3, max_length=32)


class RoleApplicationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str = Field(default="", max_length=1000)


class UserCenterProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=50)
    bio: str = Field(default="", max_length=300)
    region: str = Field(default="", max_length=100)
    profile_visibility: str = Field(pattern="^(private|members|public)$")


class UserCenterPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    history_enabled: bool
    recommendation_enabled: bool
    personalization_enabled: bool
    notification_enabled: bool


class UserCenterLibraryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    target_href: str = Field(default="", max_length=500)


class UserCenterFollowUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=200)
    target_href: str = Field(default="", max_length=500)


class UserCenterHistoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    target_href: str = Field(default="", max_length=500)
    progress_seconds: int = Field(default=0, ge=0, le=86400)
    duration_seconds: int = Field(default=0, ge=0, le=86400)


class AuthLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)
    workspace_id: str = Field(default="", max_length=100)


class AuthRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=2, max_length=40)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)


class AuthRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=40, max_length=300)


class AuthPasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class CommunityHistoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    progress_seconds: int = Field(default=0, ge=0, le=86400)


class CommunityCommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=1000)
    parent_id: str = Field(default="", max_length=64)


class CommunityAnnotationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp_seconds: int = Field(ge=0, le=86400)
    body: str = Field(min_length=1, max_length=1000)
    kind: str = Field(pattern="^(craft|term|regional_difference|source|correction)$")
    source_ids: list[str] = Field(default_factory=list, max_length=10)


class CommunitySubmissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    submission_type: str = Field(pattern="^(video|article|project|event)$")
    title: str = Field(default="", max_length=200)


class CommunitySubmissionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
    body: str | None = Field(default=None, max_length=50_000)
    categoryId: str | None = Field(default=None, max_length=100)
    regionId: str | None = Field(default=None, max_length=200)
    projectIds: list[str] | None = Field(default=None, max_length=20)
    personIds: list[str] | None = Field(default=None, max_length=20)
    sourceIds: list[str] | None = Field(default=None, max_length=20)
    tags: list[str] | None = Field(default=None, max_length=12)
    assets: list[dict[str, object]] | None = Field(default=None, max_length=20)
    assetOrder: list[str] | None = Field(default=None, max_length=20)
    aiDisclosure: str | None = Field(default=None, pattern="^(none|assisted|generated)$")


class CommunitySubmissionTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    status: str = Field(min_length=3, max_length=32)
    reviewer_note: str = Field(default="", max_length=2000)


class CommunityImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_state: dict[str, object]


class LearningEnrollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_content_id: str = Field(default="", max_length=200)


class LearningProgressComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)


class KnowledgeCardUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    expected_version: int = Field(ge=0)


class QuizAttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, int] = Field(min_length=1, max_length=100)
    expected_progress_version: int = Field(ge=0)


class TutorQuestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=2, max_length=1000)


class KnowledgeContributionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    source_title: str = Field(min_length=1, max_length=300)
    source_url: str = Field(min_length=8, max_length=1000)
    source_version: str = Field(min_length=1, max_length=100)


class KnowledgeContributionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(approved|rejected)$")
    reviewer_note: str = Field(min_length=1, max_length=2000)
    expected_version: int = Field(ge=1)


class CommerceStoreCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)


class CommerceProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2000)
    price_cents: int = Field(ge=1, le=10_000_000)
    source_note: str = Field(min_length=1, max_length=1000)
    category_slug: str = Field(default="other", min_length=1, max_length=80)
    craft_type: str = Field(default="", max_length=120)
    origin_region: str = Field(default="", max_length=120)
    season_tag: str = Field(default="", max_length=80)


class CommerceProductUpdate(CommerceProductCreate):
    expected_version: int = Field(ge=1)


class CommerceAdvisorQuestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=2, max_length=1000)


class CommerceVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class CommerceReviewRequest(CommerceVersionRequest):
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str = Field(min_length=1, max_length=1000)


class CommerceInventoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: int = Field(ge=0, le=1_000_000)
    expected_version: int = Field(ge=0)


class CommerceCartUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: int = Field(ge=1, le=99)
    expected_version: int = Field(ge=0)


class CommerceShipRequest(CommerceVersionRequest):
    tracking_note: str = Field(min_length=1, max_length=500)


class CommerceAfterSaleRequest(CommerceVersionRequest):
    reason: str = Field(min_length=1, max_length=1000)


class CommerceAfterSaleDecision(CommerceVersionRequest):
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str = Field(min_length=1, max_length=1000)


def create_app(
    repository: CreatorRepository | None = None,
    community_repository: CommunityRepository | None = None,
    commerce_repository: CommerceRepository | None = None,
    media_storage: FileSystemMediaStorage | None = None,
    learning_tutor: HeritageTutor | None = None,
    commerce_advisor: ShoppingAdvisor | None = None,
) -> FastAPI:
    validate_security_configuration()
    active_repository = repository or build_repository()
    service = CreatorService(active_repository)
    identity_service = IdentityService(active_repository)  # type: ignore[arg-type]
    user_center_service = UserCenterService(active_repository)  # type: ignore[arg-type]
    active_community_repository = community_repository or build_community_repository(
        active_repository
    )
    community_service = CommunityService(
        active_community_repository, user_center_service, media_storage
    )
    active_learning_tutor = learning_tutor or HeritageTutor()
    learning_service = LearningService(
        active_repository, active_learning_tutor
    )  # type: ignore[arg-type]
    active_commerce_repository = commerce_repository or build_commerce_repository(
        active_repository
    )
    active_media_storage = media_storage or community_service.media_storage
    commerce_service = CommerceService(
        active_commerce_repository, active_repository, commerce_advisor,
        media_storage=active_media_storage,
    )
    workbench_service = WorkbenchService(
        active_repository, active_commerce_repository, active_learning_tutor
    )  # type: ignore[arg-type]
    auth_service = AuthService(active_repository)  # type: ignore[arg-type]
    application = FastAPI(title="HAHA Creator API", version="0.2.0")
    allowed_origins = tuple(
        origin.strip()
        for origin in os.getenv(
            "HAHA_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=("GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"),
        allow_headers=(
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-CSRF-Token",
            "X-Upload-Filename",
            "X-Upload-Kind",
            "Idempotency-Key",
            "Last-Event-ID",
            "X-Request-ID",
            "X-User-ID",
            "X-Workspace-ID",
        ),
    )

    @application.exception_handler(CommunityNotFoundError)
    async def community_not_found_handler(
        _request: Request, exc: CommunityNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(CommunityPermissionError)
    async def community_permission_handler(
        _request: Request, exc: CommunityPermissionError
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @application.exception_handler(CommunityConflictError)
    async def community_conflict_handler(
        _request: Request, exc: CommunityConflictError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(CommunityValidationError)
    async def community_validation_handler(
        _request: Request, exc: CommunityValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @application.exception_handler(LearningPermissionError)
    async def learning_permission_handler(
        _request: Request, exc: LearningPermissionError
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @application.exception_handler(LearningNotFoundError)
    async def learning_not_found_handler(
        _request: Request, exc: LearningNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(LearningConflictError)
    async def learning_conflict_handler(
        _request: Request, exc: LearningConflictError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(LearningTutorUnavailableError)
    async def learning_tutor_unavailable_handler(
        _request: Request, exc: LearningTutorUnavailableError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @application.exception_handler(LearningTutorRateLimitError)
    async def learning_tutor_rate_limit_handler(
        _request: Request, exc: LearningTutorRateLimitError
    ) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @application.exception_handler(CommercePermissionError)
    async def commerce_permission_handler(
        _request: Request, exc: CommercePermissionError
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @application.exception_handler(CommerceNotFoundError)
    async def commerce_not_found_handler(
        _request: Request, exc: CommerceNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(CommerceConflictError)
    async def commerce_conflict_handler(
        _request: Request, exc: CommerceConflictError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(CommerceAdvisorUnavailableError)
    async def commerce_advisor_unavailable_handler(
        _request: Request, exc: CommerceAdvisorUnavailableError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @application.exception_handler(CommerceAdvisorRateLimitError)
    async def commerce_advisor_rate_limit_handler(
        _request: Request, exc: CommerceAdvisorRateLimitError
    ) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    def resolve_membership(
        identity: Principal = Depends(authenticate),
    ) -> Principal:
        if identity.auth_mode == "dev":
            active_repository.ensure_identity(
                identity.user_id,
                identity.workspace_id,
                role=Role.OWNER.value,
                workspace_name=identity.workspace_id,
            )
        elif not auth_service.session_is_active(
            identity.session_id, identity.user_id, identity.workspace_id
        ):
            raise HTTPException(status_code=401, detail="访问会话无效或已撤销")
        stored_role = active_repository.get_membership_role(identity.user_id, identity.workspace_id)
        if not stored_role:
            log_event(
                "authorization.membership_denied",
                user_id=identity.user_id,
                workspace_id=identity.workspace_id,
            )
            raise HTTPException(status_code=403, detail="用户不是该工作空间成员")
        try:
            role = Role(stored_role)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="工作空间成员角色无效") from exc
        principal = Principal(
            identity.user_id,
            identity.workspace_id,
            role,
            identity.auth_mode,
            identity.session_id,
        )
        log_event(
            "authorization.identity_resolved",
            user_id=principal.user_id,
            workspace_id=principal.workspace_id,
            role=principal.role.value,
            auth_mode=principal.auth_mode,
        )
        return principal

    def require_creator_access(principal: Principal) -> None:
        if principal.role in {Role.OWNER, Role.EDITOR}:
            return
        grants = active_repository.list_role_grants(
            principal.user_id, principal.workspace_id
        )
        if any(
            grant.status == "active" and grant.role in {"creator", "contributor"}
            for grant in grants
        ):
            return
        raise HTTPException(status_code=403, detail="需要已激活的创作者或知识贡献者身份")

    def community_actor(principal: Principal) -> tuple[str, str]:
        snapshot = user_center_service.bootstrap(
            principal.user_id, principal.workspace_id
        )
        profile = snapshot["profile"]
        account = snapshot["account"]
        roles = snapshot["roles"]
        assert isinstance(profile, dict)
        assert isinstance(account, dict)
        assert isinstance(roles, list)
        active_grants = {
            str(item.get("role", ""))
            for item in roles
            if isinstance(item, dict) and item.get("status") == "active"
        }
        active_context = str(profile.get("active_role", "viewer"))
        # Internal review authority is a server-side employee grant, never a
        # public context switch. It takes precedence for community moderation.
        actor_role = (
            "admin" if "admin" in active_grants
            else "reviewer" if "reviewer" in active_grants
            else active_context if active_context in {"creator", "contributor"}
            else "viewer"
        )
        return (
            actor_role,
            str(account.get("display_name", principal.user_id)),
        )

    def execute_run_locally(run_id: str) -> None:
        completed = service.execute_run(run_id)
        if completed.status.value == "FAILED":
            active_repository.record_failed_job(completed.id, completed.error_code or "run_failed")

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = normalize_request_id(request.headers.get("X-Request-ID", ""))
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        response_status = 500
        try:
            response = await call_next(request)
            response_status = response.status_code
            response.headers["X-Request-ID"] = request_id
            apply_security_headers(response)
            return response
        finally:
            duration = time.perf_counter() - started
            route = getattr(request.scope.get("route"), "path", request.url.path)
            labels = {
                "method": request.method,
                "route": str(route),
                "status": str(response_status),
            }
            metrics.add("haha_http_requests_total", **labels)
            metrics.add("haha_http_request_duration_seconds_sum", duration, **labels)
            metrics.add("haha_http_request_duration_seconds_count", **labels)
            log_event(
                "http.request.completed",
                method=request.method,
                route=str(route),
                status=response_status,
                duration_ms=round(duration * 1000, 3),
            )
            request_id_context.reset(token)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "haha-creator-api",
            "version": "0.2.0",
            "release_id": os.getenv("HAHA_RELEASE_ID", "development"),
            "git_sha": os.getenv("HAHA_GIT_SHA", "unknown"),
        }

    @application.get("/ready")
    def ready() -> dict[str, object]:
        checks: dict[str, str] = {}
        try:
            checks["database"] = "ok" if active_repository.ping() else "failed"
        except Exception:
            checks["database"] = "failed"
        redis_url = os.getenv("REDIS_URL", "").strip()
        if redis_url:
            try:
                checks["redis"] = "ok" if Redis.from_url(redis_url).ping() else "failed"
            except Exception:
                checks["redis"] = "failed"
        else:
            checks["redis"] = "not_configured"
        required = [checks["database"] == "ok"]
        if os.getenv("HAHA_ENVIRONMENT", "production").lower() in {"staging", "production"}:
            required.append(checks["redis"] == "ok")
        if not all(required):
            raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
        return {"status": "ready", "checks": checks}

    @application.get("/metrics", include_in_schema=False)
    def prometheus_metrics(_authorized: None = Depends(authorize_metrics)) -> Response:
        return Response(
            metrics.render(),
            media_type="text/plain; version=0.0.4",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @application.post("/api/projects", status_code=status.HTTP_201_CREATED)
    def create_project(
        payload: ProjectCreate, principal: Principal = Depends(resolve_membership)
    ) -> dict[str, object]:
        require_creator_access(principal)
        metrics.add("haha_projects_created_total")
        return asdict(
            service.create_project(title=payload.title, workspace_id=principal.workspace_id)
        )

    @application.get("/api/creator/model-capabilities")
    def creator_model_capabilities(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        require_creator_access(principal)
        router_status = get_model_router().status()
        return {
            "text_ready": router_status.text_ready,
            "default_model": "DeepSeek-V4.1-Flash" if router_status.text_ready else "本地演示",
            "options": [
                {
                    "id": "DeepSeek-V4.1-Flash",
                    "label": "DeepSeek V4.1 Flash",
                    "kind": "real_api",
                    "available": router_status.text_ready,
                    "notice": "调用真实模型并保存请求、模型、耗时与 Token 证据。",
                },
                {
                    "id": "DeepSeek-V4-Pro",
                    "label": "DeepSeek V4 Pro",
                    "kind": "real_api",
                    "available": router_status.text_ready,
                    "notice": "质量优先，耗时与调用成本通常高于 Flash。",
                },
                {
                    "id": "本地演示",
                    "label": "本地规则演示（非 AI）",
                    "kind": "deterministic_demo",
                    "available": True,
                    "notice": "仅执行确定性模板与知识检索，不代表模型已接通。",
                },
            ],
            "generation_limit": {"max_output_tokens": 4096, "calls_per_run": 1},
        }

    @application.post("/api/projects/{project_id}/briefs", status_code=status.HTTP_201_CREATED)
    def create_brief(
        project_id: str,
        payload: BriefCreate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            project = active_repository.get_project(project_id)
            if not project:
                raise LookupError("项目不存在")
            require_project_access(principal, project.workspace_id)
            require_creator_access(principal)
            return asdict(service.create_brief(project_id, **payload.model_dump()))
        except (LookupError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/projects/{project_id}/runs", status_code=status.HTTP_202_ACCEPTED)
    def create_run(
        project_id: str,
        payload: RunCreate,
        background_tasks: BackgroundTasks,
        principal: Principal = Depends(resolve_membership),
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
    ) -> dict[str, object]:
        try:
            project = active_repository.get_project(project_id)
            if not project:
                raise ValueError("项目不存在")
            require_project_access(principal, project.workspace_id)
            require_creator_access(principal)
            run, created = service.create_run(
                workspace_id=principal.workspace_id,
                project_id=project_id,
                brief_version_id=payload.brief_version_id,
                model_preference=payload.model_preference,
                idempotency_key=idempotency_key,
            )
        except IdempotencyConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        queued = created and enqueue_run(run.id, request_id_context.get())
        if created and not queued:
            background_tasks.add_task(execute_run_locally, run.id)
        response = asdict(run)
        response["created"] = created
        response["execution"] = "worker" if queued else "local-background"
        if created:
            metrics.add("haha_runs_created_total")
        return response

    @application.get("/api/runs/{run_id}")
    def get_run(
        run_id: str, principal: Principal = Depends(resolve_membership)
    ) -> dict[str, object]:
        run = active_repository.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        project = active_repository.get_project(run.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        require_project_access(principal, project.workspace_id)
        result = asdict(run)
        script = active_repository.get_script_for_run(run_id)
        result["script"] = asdict(script) if script else None
        revision = active_repository.get_latest_script_revision(run_id)
        result["latest_revision"] = asdict(revision) if revision else None
        return result

    @application.post("/api/runs/{run_id}/script-revisions", status_code=status.HTTP_201_CREATED)
    def create_script_revision(
        run_id: str,
        payload: ScriptRevisionCreate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        run = active_repository.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        require_project_access(principal, run.workspace_id)
        require_creator_access(principal)
        try:
            revision = service.create_script_revision(
                run_id, payload=payload.payload,
                expected_version=payload.expected_version, user_id=principal.user_id,
            )
        except ScriptRevisionConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        log_event("creator.script_revision.created", run_id=run_id, version=revision.version)
        return asdict(revision)

    @application.post("/api/runs/{run_id}/script-revisions/review")
    def review_script_revision(
        run_id: str,
        payload: ScriptRevisionReview,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        run = active_repository.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        require_project_access(principal, run.workspace_id)
        require_creator_access(principal)
        try:
            revision = service.review_script_revision(
                run_id, expected_version=payload.expected_version,
                note=payload.note, user_id=principal.user_id,
            )
        except ScriptRevisionConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        log_event("creator.script_revision.reviewed", run_id=run_id, version=revision.version)
        return asdict(revision)

    @application.get("/api/runs/{run_id}/submission-handoff")
    def get_submission_handoff(
        run_id: str, principal: Principal = Depends(resolve_membership)
    ) -> dict[str, object]:
        run = active_repository.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        require_project_access(principal, run.workspace_id)
        require_creator_access(principal)
        revision = active_repository.get_latest_script_revision(run_id)
        if not revision or revision.review_status != "reviewed":
            raise HTTPException(status_code=409, detail="完成人工修订与复核后才能进入投稿")
        payload = revision.payload
        return {
            "run_id": run_id,
            "revision_id": revision.id,
            "revision_version": revision.version,
            "title": payload.get("title", ""),
            "summary": payload.get("caption") or payload.get("hook", ""),
            "body": "\n\n".join(str(item) for item in payload.get("voiceover", [])),
            "tags": payload.get("tags", []),
            "ai_disclosure": "assisted",
            "provenance": "reviewed_creator_revision",
        }

    @application.get("/api/runs/{run_id}/events", response_class=StreamingResponse)
    def stream_run_events(
        run_id: str,
        principal: Principal = Depends(resolve_membership),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
        timeout_seconds: int = Query(default=30, ge=1, le=30),
    ) -> StreamingResponse:
        run = active_repository.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        project = active_repository.get_project(run.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        require_project_access(principal, project.workspace_id)

        async def event_stream():  # type: ignore[no-untyped-def]
            deadline = time.monotonic() + timeout_seconds
            seen_event_id = last_event_id
            yield "retry: 1000\n\n"
            while True:
                current = active_repository.get_run(run_id)
                if current is None:
                    yield _sse_event(
                        "run.deleted",
                        {"run_id": run_id, "terminal": True},
                        event_id=f"deleted:{run_id}",
                    )
                    return
                terminal = current.status in TERMINAL_RUN_STATUSES
                event_id = current.updated_at
                if event_id != seen_event_id or terminal:
                    yield _sse_event(
                        "run.terminal" if terminal else "run.status",
                        {
                            "run_id": current.id,
                            "status": current.status.value,
                            "attempt": current.attempt,
                            "updated_at": current.updated_at,
                            "error_code": current.error_code,
                            "error_message": current.error_message,
                            "terminal": terminal,
                        },
                        event_id=event_id,
                    )
                    seen_event_id = event_id
                    if terminal:
                        return
                if time.monotonic() >= deadline:
                    yield _sse_event(
                        "run.timeout",
                        {"run_id": run_id, "terminal": False},
                    )
                    return
                await asyncio.sleep(0.5)

        metrics.add("haha_run_event_streams_total")
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @application.post("/api/runs/{run_id}/cancel")
    def cancel_run(
        run_id: str, principal: Principal = Depends(resolve_membership)
    ) -> dict[str, object]:
        run = active_repository.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        project = active_repository.get_project(run.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        require_project_access(principal, project.workspace_id)
        require_creator_access(principal)
        try:
            cancelled = service.cancel_run(run_id)
        except RunNotCancellableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        metrics.add("haha_runs_cancelled_total")
        log_event(
            "run.cancelled",
            run_id=cancelled.id,
            workspace_id=principal.workspace_id,
            user_id=principal.user_id,
        )
        return asdict(cancelled)

    @application.get("/api/failed-jobs")
    def list_failed_jobs(
        principal: Principal = Depends(resolve_membership),
        include_resolved: bool = Query(default=False),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> dict[str, object]:
        jobs = active_repository.list_failed_jobs(
            principal.workspace_id,
            include_resolved=include_resolved,
            limit=limit,
        )
        items: list[dict[str, object]] = []
        for job in jobs:
            run = active_repository.get_run(job.run_id)
            if not run:
                continue
            item = asdict(job)
            item["run"] = asdict(run)
            items.append(item)
        return {"items": items, "count": len(items)}

    @application.post(
        "/api/failed-jobs/{failed_job_id}/retry",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def retry_failed_job(
        failed_job_id: str,
        background_tasks: BackgroundTasks,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        require_write_access(principal)
        try:
            retrying = service.retry_failed_job(failed_job_id, principal.workspace_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except FailedJobNotRetryableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        queued = enqueue_run(retrying.id, request_id_context.get())
        if not queued:
            background_tasks.add_task(execute_run_locally, retrying.id)
        metrics.add("haha_failed_jobs_retried_total")
        log_event(
            "failed_job.retried",
            failed_job_id=failed_job_id,
            run_id=retrying.id,
            workspace_id=principal.workspace_id,
            user_id=principal.user_id,
        )
        job = active_repository.get_failed_job(failed_job_id, principal.workspace_id)
        return {
            "failed_job": asdict(job) if job else None,
            "run": asdict(retrying),
            "execution": "worker" if queued else "local-background",
        }

    @application.post("/api/failed-jobs/{failed_job_id}/resolve")
    def resolve_failed_job(
        failed_job_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        require_write_access(principal)
        try:
            job = service.resolve_failed_job(failed_job_id, principal.workspace_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        metrics.add("haha_failed_jobs_resolved_total")
        log_event(
            "failed_job.resolved",
            failed_job_id=failed_job_id,
            run_id=job.run_id,
            workspace_id=principal.workspace_id,
            user_id=principal.user_id,
        )
        return asdict(job)

    @application.get("/api/identity/me")
    def get_identity_center(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        """Return server-authoritative business roles and durable workspace context."""
        return identity_service.bootstrap(principal.user_id, principal.workspace_id)

    @application.post("/api/identity/roles/{role}/activate")
    def activate_business_role(
        role: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        identity_service.bootstrap(principal.user_id, principal.workspace_id)
        try:
            snapshot = identity_service.activate_role(
                principal.user_id, principal.workspace_id, role
            )
        except IdentityPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        metrics.add("haha_identity_roles_activated_total", role=role)
        return snapshot

    @application.post("/api/identity/role-applications", status_code=status.HTTP_201_CREATED)
    def create_role_application(
        payload: RoleApplicationCreate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        identity_service.bootstrap(principal.user_id, principal.workspace_id)
        try:
            application = identity_service.apply_for_role(
                principal.user_id, principal.workspace_id, payload.role, payload.reason
            )
        except IdentityPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except IdentityConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        metrics.add("haha_identity_role_applications_total", role=payload.role)
        return asdict(application)

    @application.post("/api/identity/context")
    def switch_identity_context(
        payload: IdentityContextSwitch,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        identity_service.bootstrap(principal.user_id, principal.workspace_id)
        try:
            return identity_service.switch_context(
                principal.user_id, principal.workspace_id, payload.role
            )
        except IdentityPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/identity/tasks/{task_id}/complete")
    def complete_identity_task(
        task_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return asdict(
                identity_service.complete_task(task_id, principal.user_id, principal.workspace_id)
            )
        except IdentityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/api/identity/workbench")
    def get_identity_workbench(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        """Return the server-authoritative projection for the active business role."""
        try:
            return workbench_service.snapshot(principal.user_id, principal.workspace_id)
        except WorkbenchPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @application.get("/api/platform/capabilities")
    def get_platform_capabilities(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        """Return account capabilities independently from the selected workbench."""
        return workbench_service.platform_capabilities(
            principal.user_id, principal.workspace_id
        )

    @application.post("/api/identity/role-applications/{application_id}/decision")
    def decide_role_application(
        application_id: str,
        payload: RoleApplicationDecision,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        if principal.role is not Role.OWNER:
            raise HTTPException(status_code=403, detail="仅工作空间所有者可以审核身份申请")
        try:
            application = identity_service.decide_application(
                application_id, principal.user_id, payload.decision, payload.note
            )
        except IdentityPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except IdentityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except IdentityConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        metrics.add("haha_identity_role_decisions_total", decision=payload.decision)
        return asdict(application)

    @application.post("/api/auth/login")
    def login(payload: AuthLoginRequest) -> dict[str, object]:
        try:
            result = auth_service.login(**payload.model_dump())
        except InvalidCredentialsError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AccountLockedError as exc:
            raise HTTPException(
                status_code=429, detail=str(exc), headers={"Retry-After": "900"}
            ) from exc
        metrics.add("haha_auth_login_success_total")
        return result

    @application.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
    def register_account(payload: AuthRegistrationRequest) -> dict[str, object]:
        try:
            result = auth_service.register(**payload.model_dump())
        except RegistrationDisabledError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except AccountRegistrationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        metrics.add("haha_auth_registration_success_total")
        return result

    @application.post("/api/auth/refresh")
    def refresh_auth_session(payload: AuthRefreshRequest) -> dict[str, object]:
        try:
            result = auth_service.refresh(payload.refresh_token)
        except InvalidRefreshTokenError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        metrics.add("haha_auth_refresh_success_total")
        return result

    @application.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    def logout(payload: AuthRefreshRequest) -> Response:
        auth_service.logout(payload.refresh_token)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.get("/api/auth/me")
    def get_authenticated_account(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, str]:
        return {
            "user_id": principal.user_id,
            "workspace_id": principal.workspace_id,
            "role": principal.role.value,
            "auth_mode": principal.auth_mode,
        }

    @application.get("/api/auth/sessions")
    def list_auth_sessions(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        items = auth_service.list_sessions(
            user_id=principal.user_id,
            workspace_id=principal.workspace_id,
            current_session_id=principal.session_id,
        )
        return {"items": items, "count": len(items)}

    @application.delete("/api/auth/sessions/{session_id}")
    def revoke_auth_session(
        session_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        revoked = auth_service.revoke_session(
            session_id=session_id,
            user_id=principal.user_id,
            workspace_id=principal.workspace_id,
        )
        if not revoked:
            raise HTTPException(status_code=404, detail="登录会话不存在或已撤销")
        return {"revoked": True, "session_id": session_id}

    @application.delete("/api/auth/sessions")
    def revoke_all_auth_sessions(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, int]:
        return {
            "revoked": auth_service.revoke_all_sessions(
                user_id=principal.user_id,
                workspace_id=principal.workspace_id,
            )
        }

    @application.post("/api/auth/password/change")
    def change_auth_password(
        payload: AuthPasswordChangeRequest,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            revoked = auth_service.change_password(
                user_id=principal.user_id,
                workspace_id=principal.workspace_id,
                **payload.model_dump(),
            )
        except InvalidCredentialsError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AccountLockedError as exc:
            raise HTTPException(
                status_code=429, detail=str(exc), headers={"Retry-After": "900"}
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        metrics.add("haha_auth_password_changes_total")
        return {
            "changed": True,
            "revoked_sessions": revoked,
            "requires_login": True,
        }

    @application.get("/api/user-center")
    def get_user_center(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return user_center_service.bootstrap(principal.user_id, principal.workspace_id)

    @application.get("/api/user-center/export")
    def export_user_center_data(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        snapshot = user_center_service.bootstrap(
            principal.user_id, principal.workspace_id
        )
        credential = active_repository.get_auth_credential_by_user(
            principal.user_id, principal.workspace_id
        )
        sessions = auth_service.list_sessions(
            user_id=principal.user_id,
            workspace_id=principal.workspace_id,
            current_session_id=principal.session_id,
        )
        return {
            "schema_version": "haha-account-export.v1",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "account": {
                "user_id": principal.user_id,
                "workspace_id": principal.workspace_id,
                "email": credential.email if credential else "",
                "credential_status": credential.status if credential else "unknown",
            },
            "user_center": snapshot,
            "security": {
                "sessions": sessions,
                "password_hashes_included": False,
                "refresh_tokens_included": False,
                "internal_audit_included": False,
            },
            "scope_note": (
                "本导出包含当前个人空间中的用户中心、身份、学习成长摘要和会话元数据；"
                "不包含密码、令牌、内部风控审计或其他账户数据。"
            ),
        }

    @application.patch("/api/user-center/profile")
    def update_user_center_profile(
        payload: UserCenterProfileUpdate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return user_center_service.update_profile(
                principal.user_id, principal.workspace_id, **payload.model_dump()
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.patch("/api/user-center/preferences")
    def update_user_center_preferences(
        payload: UserCenterPreferencesUpdate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return user_center_service.update_preferences(
            principal.user_id, principal.workspace_id, **payload.model_dump()
        )

    @application.put("/api/user-center/library/{kind}/{target_id}")
    def save_user_center_library_item(
        kind: str,
        target_id: str,
        payload: UserCenterLibraryUpdate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return user_center_service.set_library_item(
                principal.user_id,
                principal.workspace_id,
                kind_value=kind,
                target_id=target_id,
                active=True,
                **payload.model_dump(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.delete("/api/user-center/library/{kind}/{target_id}")
    def delete_user_center_library_item(
        kind: str,
        target_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return user_center_service.set_library_item(
                principal.user_id,
                principal.workspace_id,
                kind_value=kind,
                target_id=target_id,
                title="",
                target_href="",
                active=False,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.put("/api/user-center/follows/{target_id}")
    def save_user_center_follow(
        target_id: str,
        payload: UserCenterFollowUpdate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return user_center_service.set_follow(
                principal.user_id,
                principal.workspace_id,
                target_id=target_id,
                active=True,
                **payload.model_dump(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.delete("/api/user-center/follows/{target_id}")
    def delete_user_center_follow(
        target_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return user_center_service.set_follow(
                principal.user_id,
                principal.workspace_id,
                target_id=target_id,
                display_name="",
                target_href="",
                active=False,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.delete("/api/user-center/history")
    def clear_user_center_history(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return {
            "removed": user_center_service.clear_history(principal.user_id, principal.workspace_id)
        }

    @application.put("/api/user-center/history/{content_id}")
    def save_user_center_history(
        content_id: str,
        payload: UserCenterHistoryUpdate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            item = user_center_service.record_history(
                principal.user_id,
                principal.workspace_id,
                content_id=content_id,
                **payload.model_dump(),
            )
            return {"item": asdict(item) if item else None}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.delete("/api/user-center/history/{content_id}")
    def delete_user_center_history(
        content_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, bool]:
        user_center_service.remove_history_item(
            principal.user_id, principal.workspace_id, content_id
        )
        return {"deleted": True}

    @application.post("/api/user-center/notifications/{notification_id}/read")
    def read_user_center_notification(
        notification_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return asdict(
                user_center_service.mark_notification_read(
                    notification_id, principal.user_id, principal.workspace_id
                )
            )
        except UserCenterNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.delete("/api/user-center/notifications/{notification_id}")
    def delete_user_center_notification(
        notification_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, bool]:
        try:
            user_center_service.delete_notification(
                notification_id, principal.user_id, principal.workspace_id
            )
        except UserCenterNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"deleted": True}

    @application.get("/api/learning")
    def get_learning_center(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        """Return the learner-owned, server-authoritative growth snapshot."""
        return learning_service.bootstrap(principal.user_id, principal.workspace_id)

    @application.post("/api/learning/paths/{path_id}/enroll")
    def enroll_learning_path(
        path_id: str,
        payload: LearningEnrollRequest,
        principal: Principal = Depends(resolve_membership),
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=200
        ),
    ) -> dict[str, object]:
        try:
            return learning_service.enroll_path(
                principal.user_id,
                principal.workspace_id,
                path_id,
                source_content_id=payload.source_content_id,
                idempotency_key=idempotency_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/learning/units/{unit_id}/complete")
    def complete_learning_unit(
        unit_id: str,
        payload: LearningProgressComplete,
        principal: Principal = Depends(resolve_membership),
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=200
        ),
    ) -> dict[str, object]:
        return learning_service.complete_unit(
            principal.user_id,
            principal.workspace_id,
            unit_id,
            expected_version=payload.expected_version,
            idempotency_key=idempotency_key,
        )

    @application.put("/api/learning/cards/{unit_id}")
    def save_learning_knowledge_card(
        unit_id: str,
        payload: KnowledgeCardUpsert,
        principal: Principal = Depends(resolve_membership),
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=200
        ),
    ) -> dict[str, object]:
        try:
            return learning_service.save_knowledge_card(
                principal.user_id,
                principal.workspace_id,
                unit_id,
                idempotency_key=idempotency_key,
                **payload.model_dump(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/learning/quizzes/{quiz_id}/attempts")
    def submit_learning_quiz(
        quiz_id: str,
        payload: QuizAttemptCreate,
        principal: Principal = Depends(resolve_membership),
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=200
        ),
    ) -> dict[str, object]:
        try:
            return learning_service.submit_quiz(
                principal.user_id,
                principal.workspace_id,
                quiz_id,
                idempotency_key=idempotency_key,
                **payload.model_dump(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/learning/tutor/questions")
    def ask_learning_tutor(
        payload: TutorQuestionCreate,
        principal: Principal = Depends(resolve_membership),
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=200
        ),
    ) -> dict[str, object]:
        try:
            return learning_service.ask_tutor(
                principal.user_id,
                principal.workspace_id,
                question=payload.question,
                idempotency_key=idempotency_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/learning/contributions")
    def submit_learning_contribution(
        payload: KnowledgeContributionCreate,
        principal: Principal = Depends(resolve_membership),
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=200
        ),
    ) -> dict[str, object]:
        try:
            return learning_service.submit_knowledge_contribution(
                principal.user_id,
                principal.workspace_id,
                idempotency_key=idempotency_key,
                **payload.model_dump(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/learning/contributions/review-queue")
    def get_learning_contribution_review_queue(
        principal: Principal = Depends(resolve_membership),
    ) -> list[dict[str, object]]:
        return learning_service.review_queue(
            principal.user_id, principal.workspace_id
        )

    @application.post("/api/learning/contributions/{contribution_id}/review")
    def review_learning_contribution(
        contribution_id: str,
        payload: KnowledgeContributionReview,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return asdict(learning_service.review_knowledge_contribution(
                principal.user_id,
                principal.workspace_id,
                contribution_id,
                **payload.model_dump(),
            ))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/commerce")
    def get_commerce_center(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        """Return account-scoped commerce state with explicit sandbox boundaries."""
        return commerce_service.snapshot(principal.user_id, principal.workspace_id)

    @application.get("/api/commerce/catalog")
    def search_commerce_catalog(
        q: str = Query(default="", max_length=200),
        category: str = Query(default="", max_length=80),
        craft_type: str = Query(default="", max_length=120),
        origin_region: str = Query(default="", max_length=120),
        season_tag: str = Query(default="", max_length=80),
        sort: str = Query(default="newest", pattern="^(newest|price_asc|price_desc)$"),
        page: int = Query(default=1, ge=1, le=10_000),
        page_size: int = Query(default=24, ge=1, le=60),
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return commerce_service.catalog(
                principal.user_id,
                principal.workspace_id,
                query=q,
                category=category,
                craft_type=craft_type,
                origin_region=origin_region,
                season_tag=season_tag,
                sort=sort,
                page=page,
                page_size=page_size,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/commerce/products/{product_id}")
    def get_commerce_product_detail(
        product_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return commerce_service.product_detail(
            principal.user_id, principal.workspace_id, product_id
        )

    @application.get("/api/commerce/advisor")
    def get_commerce_advisor(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return commerce_service.advisor_snapshot(
            principal.user_id, principal.workspace_id
        )

    @application.post("/api/commerce/advisor/messages")
    def ask_commerce_advisor(
        payload: CommerceAdvisorQuestionCreate,
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=200
        ),
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return commerce_service.ask_advisor(
                principal.user_id,
                principal.workspace_id,
                question=payload.question,
                idempotency_key=idempotency_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/commerce/stores")
    def open_commerce_store(
        payload: CommerceStoreCreate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return commerce_service.open_store(
                principal.user_id, principal.workspace_id, payload.name
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/commerce/products", status_code=status.HTTP_201_CREATED)
    def create_commerce_product(
        payload: CommerceProductCreate,
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=200
        ),
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return commerce_service.create_product(
                principal.user_id,
                principal.workspace_id,
                idempotency_key=idempotency_key,
                **payload.model_dump(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.put("/api/commerce/products/{product_id}")
    def update_commerce_product(
        product_id: str,
        payload: CommerceProductUpdate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            values = payload.model_dump()
            expected_version = values.pop("expected_version")
            return commerce_service.update_product_details(
                principal.user_id, principal.workspace_id, product_id,
                expected_version=expected_version, **values,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.put("/api/commerce/products/{product_id}/images")
    async def upload_commerce_product_image(
        product_id: str,
        request: Request,
        expected_version: int = Query(ge=1),
        original_name: str = Header(alias="X-Upload-Filename", min_length=1, max_length=255),
        alt_text: str = Header(alias="X-Image-Alt", min_length=1, max_length=300),
        source_note: str = Header(alias="X-Image-Source", min_length=1, max_length=1000),
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        maximum = 10 * 1024 * 1024
        declared_length = request.headers.get("content-length", "")
        try:
            if declared_length and int(declared_length) > maximum:
                raise HTTPException(status_code=413, detail="商品图片不能超过 10 MB")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Content-Length 无效") from exc
        staged_path = commerce_service.media_storage.create_staging_path()
        byte_size = 0
        try:
            with staged_path.open("wb") as handle:
                async for chunk in request.stream():
                    byte_size += len(chunk)
                    if byte_size > maximum:
                        raise HTTPException(status_code=413, detail="商品图片不能超过 10 MB")
                    handle.write(chunk)
            try:
                return commerce_service.add_product_image(
                    principal.user_id, principal.workspace_id, product_id,
                    staged_path=staged_path, filename=unquote(original_name),
                    declared_content_type=request.headers.get("content-type", "").split(";", 1)[0].strip().lower(),
                    alt_text=unquote(alt_text), source_note=unquote(source_note),
                    expected_version=expected_version,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            commerce_service.media_storage.discard(staged_path)

    @application.delete("/api/commerce/products/{product_id}/images/{media_id}")
    def delete_commerce_product_image(
        product_id: str,
        media_id: str,
        expected_version: int = Query(ge=1),
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return commerce_service.remove_product_image(
            principal.user_id, principal.workspace_id, product_id, media_id,
            expected_version,
        )

    @application.get("/api/commerce/media/{media_id}")
    def get_commerce_product_image(
        media_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> FileResponse:
        path, content_type = commerce_service.product_image_path(
            principal.user_id, principal.workspace_id, media_id
        )
        return FileResponse(
            path, media_type=content_type, content_disposition_type="inline",
            headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
        )

    @application.post("/api/commerce/products/{product_id}/submit")
    def submit_commerce_product(
        product_id: str,
        payload: CommerceVersionRequest,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return commerce_service.submit_product(
            principal.user_id,
            principal.workspace_id,
            product_id,
            payload.expected_version,
        )

    @application.post("/api/commerce/products/{product_id}/review")
    def review_commerce_product(
        product_id: str,
        payload: CommerceReviewRequest,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return commerce_service.moderate_product(
                principal.user_id,
                principal.workspace_id,
                product_id,
                payload.decision,
                payload.note,
                payload.expected_version,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.put("/api/commerce/products/{product_id}/inventory")
    def update_commerce_inventory(
        product_id: str,
        payload: CommerceInventoryUpdate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return commerce_service.set_inventory(
                principal.user_id,
                principal.workspace_id,
                product_id,
                payload.quantity,
                payload.expected_version,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.put("/api/commerce/cart/{product_id}")
    def update_commerce_cart(
        product_id: str,
        payload: CommerceCartUpdate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return commerce_service.set_cart_item(
            principal.user_id,
            principal.workspace_id,
            product_id,
            payload.quantity,
            payload.expected_version,
        )

    @application.delete("/api/commerce/cart/{product_id}")
    def delete_commerce_cart_item(
        product_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return commerce_service.remove_cart_item(
            principal.user_id, principal.workspace_id, product_id
        )

    @application.post("/api/commerce/checkout")
    def checkout_commerce_cart(
        principal: Principal = Depends(resolve_membership),
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=200
        ),
    ) -> dict[str, object]:
        try:
            return commerce_service.checkout(
                principal.user_id, principal.workspace_id, idempotency_key
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/commerce/orders/{order_id}/sandbox-payment")
    def authorize_commerce_sandbox_payment(
        order_id: str,
        payload: CommerceVersionRequest,
        principal: Principal = Depends(resolve_membership),
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=200
        ),
    ) -> dict[str, object]:
        try:
            return commerce_service.sandbox_pay(
                principal.user_id,
                principal.workspace_id,
                order_id,
                payload.expected_version,
                idempotency_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/commerce/orders/{order_id}/cancel")
    def cancel_commerce_order(
        order_id: str,
        payload: CommerceVersionRequest,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return commerce_service.cancel_order(
            principal.user_id,
            principal.workspace_id,
            order_id,
            payload.expected_version,
        )

    @application.post("/api/commerce/orders/{order_id}/ship")
    def ship_commerce_order(
        order_id: str,
        payload: CommerceShipRequest,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return commerce_service.ship_order(
                principal.user_id,
                principal.workspace_id,
                order_id,
                payload.tracking_note,
                payload.expected_version,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/commerce/orders/{order_id}/confirm-delivery")
    def confirm_commerce_delivery(
        order_id: str,
        payload: CommerceVersionRequest,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return commerce_service.confirm_delivery(
            principal.user_id,
            principal.workspace_id,
            order_id,
            payload.expected_version,
        )

    @application.post("/api/commerce/orders/{order_id}/after-sales")
    def request_commerce_after_sale(
        order_id: str,
        payload: CommerceAfterSaleRequest,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return commerce_service.request_after_sale(
                principal.user_id,
                principal.workspace_id,
                order_id,
                payload.reason,
                payload.expected_version,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/commerce/after-sales/{after_sale_id}/decision")
    def decide_commerce_after_sale(
        after_sale_id: str,
        payload: CommerceAfterSaleDecision,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        try:
            return commerce_service.decide_after_sale(
                principal.user_id,
                principal.workspace_id,
                after_sale_id,
                payload.decision,
                payload.note,
                payload.expected_version,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/community/bootstrap")
    def get_community_bootstrap(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return community_service.bootstrap(principal.user_id, principal.workspace_id)

    @application.get("/api/community/feed")
    def get_community_feed(
        mode: str = Query(default="recommended", pattern="^(recommended|following|nearby|learning)$"),
        channel_id: str = Query(default="", max_length=100),
        region_id: str = Query(default="", max_length=200),
        cursor: int = Query(default=0, ge=0),
        limit: int = Query(default=20, ge=1, le=50),
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return community_service.feed(
            principal.user_id,
            principal.workspace_id,
            mode=mode,
            channel_id=channel_id,
            region_id=region_id,
            cursor=cursor,
            limit=limit,
        )

    @application.get("/api/community/contents/{content_id}")
    def get_community_content(
        content_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return community_service.content(
            principal.user_id, principal.workspace_id, content_id
        )

    @application.get("/api/community/search")
    def search_community(
        q: str = Query(min_length=1, max_length=100),
        scope: str = Query(default="all", pattern="^(all|content|project|person|region)$"),
        sort: str = Query(
            default="relevance",
            pattern="^(relevance|latest|popular|verified)$",
        ),
        cursor: int = Query(default=0, ge=0),
        limit: int = Query(default=20, ge=1, le=50),
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return community_service.search(
            principal.user_id,
            principal.workspace_id,
            query=q,
            scope=scope,
            sort=sort,
            cursor=cursor,
            limit=limit,
        )

    @application.put("/api/community/contents/{content_id}/reactions/{reaction}")
    def save_community_reaction(
        content_id: str,
        reaction: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return community_service.set_reaction(
            principal.user_id, principal.workspace_id, content_id, reaction, True
        )

    @application.delete("/api/community/contents/{content_id}/reactions/{reaction}")
    def delete_community_reaction(
        content_id: str,
        reaction: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return community_service.set_reaction(
            principal.user_id, principal.workspace_id, content_id, reaction, False
        )

    @application.put("/api/community/people/{person_id}/follow")
    def save_community_follow(
        person_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return community_service.set_follow(
            principal.user_id, principal.workspace_id, person_id, True
        )

    @application.delete("/api/community/people/{person_id}/follow")
    def delete_community_follow(
        person_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return community_service.set_follow(
            principal.user_id, principal.workspace_id, person_id, False
        )

    @application.put("/api/community/contents/{content_id}/history")
    def save_community_history(
        content_id: str,
        payload: CommunityHistoryUpdate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return community_service.record_history(
            principal.user_id,
            principal.workspace_id,
            content_id,
            payload.progress_seconds,
        )

    @application.delete("/api/community/contents/{content_id}/history")
    def delete_community_history(
        content_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, bool]:
        community_service.remove_history(
            principal.user_id, principal.workspace_id, content_id
        )
        return {"deleted": True}

    @application.post(
        "/api/community/contents/{content_id}/comments",
        status_code=status.HTTP_201_CREATED,
    )
    def create_community_comment(
        content_id: str,
        payload: CommunityCommentCreate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        _, display_name = community_actor(principal)
        return community_service.create_comment(
            principal.user_id,
            principal.workspace_id,
            display_name,
            content_id,
            payload.body,
            payload.parent_id,
        )

    @application.delete("/api/community/comments/{comment_id}")
    def delete_community_comment(
        comment_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, bool]:
        community_service.delete_comment(
            principal.user_id, principal.workspace_id, comment_id
        )
        return {"deleted": True}

    @application.post(
        "/api/community/contents/{content_id}/annotations",
        status_code=status.HTTP_201_CREATED,
    )
    def create_community_annotation(
        content_id: str,
        payload: CommunityAnnotationCreate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        _, display_name = community_actor(principal)
        return community_service.create_annotation(
            principal.user_id,
            principal.workspace_id,
            display_name,
            content_id,
            **payload.model_dump(),
        )

    @application.delete("/api/community/annotations/{annotation_id}")
    def delete_community_annotation(
        annotation_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, bool]:
        community_service.delete_annotation(
            principal.user_id, principal.workspace_id, annotation_id
        )
        return {"deleted": True}

    @application.get("/api/community/submissions")
    def list_community_submissions(
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        role, _ = community_actor(principal)
        items = community_service.list_submissions(
            principal.user_id, principal.workspace_id, role
        )
        return {"items": items, "count": len(items)}

    @application.post(
        "/api/community/submissions", status_code=status.HTTP_201_CREATED
    )
    def create_community_submission(
        payload: CommunitySubmissionCreate,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        role, _ = community_actor(principal)
        return community_service.create_submission(
            principal.user_id,
            principal.workspace_id,
            role,
            payload.submission_type,
            payload.title,
        )

    @application.get("/api/community/submissions/{submission_id}")
    def get_community_submission(
        submission_id: str,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        role, _ = community_actor(principal)
        return community_service.get_submission(
            principal.user_id, principal.workspace_id, role, submission_id
        )

    @application.patch("/api/community/submissions/{submission_id}")
    def update_community_submission(
        submission_id: str,
        payload: CommunitySubmissionPatch,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        role, _ = community_actor(principal)
        patch = payload.model_dump(exclude={"expected_version"}, exclude_none=True)
        return community_service.update_submission(
            principal.user_id,
            principal.workspace_id,
            role,
            submission_id,
            payload.expected_version,
            patch,
        )

    @application.post("/api/community/submissions/{submission_id}/transition")
    def transition_community_submission(
        submission_id: str,
        payload: CommunitySubmissionTransition,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        role, _ = community_actor(principal)
        return community_service.transition_submission(
            principal.user_id,
            principal.workspace_id,
            role,
            submission_id,
            payload.expected_version,
            payload.status,
            payload.reviewer_note,
        )

    @application.put("/api/community/submissions/{submission_id}/assets")
    async def upload_community_submission_asset(
        submission_id: str,
        request: Request,
        expected_version: int = Query(ge=1),
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
        original_name: str = Header(alias="X-Upload-Filename", min_length=1, max_length=255),
        kind: str = Header(alias="X-Upload-Kind", pattern="^(video|image)$"),
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        role, _ = community_actor(principal)
        declared_mime_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        maximum = 25 * 1024 * 1024 if kind == "video" else 15 * 1024 * 1024
        declared_length = request.headers.get("content-length", "")
        try:
            if declared_length and int(declared_length) > maximum:
                raise HTTPException(status_code=413, detail="素材大小超过服务端限制")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Content-Length 无效") from exc
        staged_path = community_service.media_storage.create_staging_path()
        digest = hashlib.sha256()
        byte_size = 0
        try:
            with staged_path.open("wb") as handle:
                async for chunk in request.stream():
                    byte_size += len(chunk)
                    if byte_size > maximum:
                        raise HTTPException(status_code=413, detail="素材大小超过服务端限制")
                    digest.update(chunk)
                    handle.write(chunk)
            return community_service.upload_submission_asset(
                principal.user_id,
                principal.workspace_id,
                role,
                submission_id,
                expected_version,
                staged_path=staged_path,
                original_name=unquote(original_name),
                kind=kind,
                declared_mime_type=declared_mime_type,
                byte_size=byte_size,
                sha256=digest.hexdigest(),
                idempotency_key=idempotency_key,
            )
        finally:
            community_service.media_storage.discard(staged_path)

    @application.delete(
        "/api/community/submissions/{submission_id}/assets/{asset_id}"
    )
    def delete_community_submission_asset(
        submission_id: str,
        asset_id: str,
        expected_version: int = Query(ge=1),
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        role, _ = community_actor(principal)
        return community_service.delete_submission_asset(
            principal.user_id,
            principal.workspace_id,
            role,
            submission_id,
            asset_id,
            expected_version,
        )

    @application.get("/api/community/media/{asset_id}")
    def get_published_community_media(asset_id: str) -> FileResponse:
        asset, path = community_service.get_published_media(asset_id)
        return FileResponse(
            path,
            media_type=asset.detected_mime_type,
            filename=asset.original_name,
            content_disposition_type="inline",
            headers={
                "Cache-Control": "public, max-age=3600",
                "ETag": f'"{asset.sha256}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    @application.post("/api/community/imports/preview")
    def preview_community_import(
        payload: CommunityImportRequest,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        return community_service.preview_import(
            principal.user_id, principal.workspace_id, payload.local_state
        )

    @application.post("/api/community/imports/commit")
    def commit_community_import(
        payload: CommunityImportRequest,
        principal: Principal = Depends(resolve_membership),
    ) -> dict[str, object]:
        _, display_name = community_actor(principal)
        return community_service.commit_import(
            principal.user_id,
            principal.workspace_id,
            display_name,
            payload.local_state,
        )

    return application


def _sse_event(event: str, payload: dict[str, object], *, event_id: str = "") -> str:
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append("data: " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines) + "\n\n"


app = create_app()
