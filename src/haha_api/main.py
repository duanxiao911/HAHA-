"""FastAPI entry point. Business behavior remains in the framework-free core."""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import asdict
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
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from redis import Redis

from haha_api.auth import (
    Principal,
    Role,
    authenticate,
    require_project_access,
    require_write_access,
    validate_security_configuration,
)
from haha_api.observability import log_event, metrics, request_id_context
from haha_core.bootstrap import build_repository, enqueue_run
from haha_core.domain import TERMINAL_RUN_STATUSES
from haha_core.repository import CreatorRepository
from haha_core.service import (
    CreatorService,
    FailedJobNotRetryableError,
    IdempotencyConflictError,
    RunNotCancellableError,
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
    model_preference: str = "本地演示"


def create_app(repository: CreatorRepository | None = None) -> FastAPI:
    validate_security_configuration()
    active_repository = repository or build_repository()
    service = CreatorService(active_repository)
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
        allow_methods=("GET", "POST", "OPTIONS"),
        allow_headers=("Authorization", "Content-Type", "Idempotency-Key", "Last-Event-ID", "X-Request-ID", "X-User-ID", "X-Workspace-ID"),
    )

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
        stored_role = active_repository.get_membership_role(
            identity.user_id, identity.workspace_id
        )
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
            identity.user_id, identity.workspace_id, role, identity.auth_mode
        )
        log_event(
            "authorization.identity_resolved",
            user_id=principal.user_id,
            workspace_id=principal.workspace_id,
            role=principal.role.value,
            auth_mode=principal.auth_mode,
        )
        return principal

    def execute_run_locally(run_id: str) -> None:
        completed = service.execute_run(run_id)
        if completed.status.value == "FAILED":
            active_repository.record_failed_job(
                completed.id, completed.error_code or "run_failed"
            )

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        response_status = 500
        try:
            response = await call_next(request)
            response_status = response.status_code
            response.headers["X-Request-ID"] = request_id
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
        if os.getenv("HAHA_ENVIRONMENT", "development").lower() in {"staging", "production"}:
            required.append(checks["redis"] == "ok")
        if not all(required):
            raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
        return {"status": "ready", "checks": checks}

    @application.get("/metrics", include_in_schema=False)
    def prometheus_metrics() -> Response:
        return Response(metrics.render(), media_type="text/plain; version=0.0.4")

    @application.post("/api/projects", status_code=status.HTTP_201_CREATED)
    def create_project(
        payload: ProjectCreate, principal: Principal = Depends(resolve_membership)
    ) -> dict[str, object]:
        require_write_access(principal)
        metrics.add("haha_projects_created_total")
        return asdict(
            service.create_project(title=payload.title, workspace_id=principal.workspace_id)
        )

    @application.post(
        "/api/projects/{project_id}/briefs", status_code=status.HTTP_201_CREATED
    )
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
            require_write_access(principal)
            return asdict(service.create_brief(project_id, **payload.model_dump()))
        except (LookupError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post(
        "/api/projects/{project_id}/runs", status_code=status.HTTP_202_ACCEPTED
    )
    def create_run(
        project_id: str,
        payload: RunCreate,
        background_tasks: BackgroundTasks,
        principal: Principal = Depends(resolve_membership),
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=200
        ),
    ) -> dict[str, object]:
        try:
            project = active_repository.get_project(project_id)
            if not project:
                raise ValueError("项目不存在")
            require_project_access(principal, project.workspace_id)
            require_write_access(principal)
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
        return result

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
        require_write_access(principal)
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

    return application


def _sse_event(event: str, payload: dict[str, object], *, event_id: str = "") -> str:
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(
        "data: " + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )
    return "\n".join(lines) + "\n\n"


app = create_app()
