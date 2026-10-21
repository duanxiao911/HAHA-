"""Application service coordinating immutable briefs, runs and script versions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from threading import Event, Thread
from typing import Any

from haha_core.domain import (
    BriefVersion,
    FailedJob,
    Project,
    Run,
    RunStatus,
    ScriptVersion,
    new_id,
    utc_now,
)
from haha_core.repository import CreatorRepository, RepositoryConflictError
from haha_core.verifier import verification_to_dict, verify_script
from haha_media.script_writer import ContentBrief, generate_content_script_for_mode


class IdempotencyConflictError(ValueError):
    """The same scoped key was reused with a different request body."""


class RunNotCancellableError(ValueError):
    """A terminal Run cannot transition to CANCELLED."""


class FailedJobNotRetryableError(ValueError):
    """A failed job cannot consume another bounded retry attempt."""


class _RunLeaseKeeper:
    """Renew an owned run lease while a blocking model/retrieval call is in flight."""

    def __init__(
        self,
        repository: CreatorRepository,
        run_id: str,
        worker_id: str,
        claim_epoch: int,
        *,
        interval_seconds: float = 30.0,
    ) -> None:
        self.repository = repository
        self.run_id = run_id
        self.worker_id = worker_id
        self.claim_epoch = claim_epoch
        self.interval_seconds = interval_seconds
        self._stop = Event()
        self._ready = Event()
        self._error: Exception | None = None
        self._thread = Thread(target=self._renew, name=f"lease-{run_id}", daemon=True)

    def _renew(self) -> None:
        try:
            while not self._stop.is_set():
                if not self.repository.heartbeat_run(
                    self.run_id, self.worker_id, self.claim_epoch
                ):
                    self._error = RepositoryConflictError("worker lost the run lease")
                    return
                self._ready.set()
                if self._stop.wait(self.interval_seconds):
                    return
        except Exception as exc:  # pragma: no cover - adapter-specific failure path
            self._error = exc
        finally:
            self._ready.set()

    def __enter__(self) -> _RunLeaseKeeper:
        self._thread.start()
        self._ready.wait()
        self.ensure_owned()
        return self

    def ensure_owned(self) -> None:
        if self._error:
            raise RepositoryConflictError("worker could not renew the run lease") from self._error

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join(timeout=max(self.interval_seconds, 1.0) + 1.0)
        self.ensure_owned()


class CreatorService:
    max_run_attempts = 3

    def __init__(self, repository: CreatorRepository) -> None:
        self.repository = repository

    def create_project(self, *, title: str, workspace_id: str) -> Project:
        if not title.strip() or not workspace_id.strip():
            raise ValueError("项目名称和工作空间不能为空")
        project = Project.create(title, workspace_id)
        self.repository.save_project(project)
        return project

    def create_brief(self, project_id: str, **data: str) -> BriefVersion:
        if not self.repository.get_project(project_id):
            raise LookupError("项目不存在")
        required = ("craft", "audience", "platform", "tone", "duration", "aspect_ratio")
        missing = [field for field in required if not str(data.get(field, "")).strip()]
        if missing:
            raise ValueError(f"缺少必需参数：{', '.join(missing)}")
        brief = BriefVersion(
            id=new_id("brief"),
            project_id=project_id,
            version=self.repository.next_brief_version(project_id),
            craft=data["craft"].strip(),
            story_seed=data.get("story_seed", "").strip(),
            audience=data["audience"].strip(),
            platform=data["platform"].strip(),
            tone=data["tone"].strip(),
            goal=data.get("goal", "文化科普").strip(),
            duration=data["duration"].strip(),
            aspect_ratio=data["aspect_ratio"].strip(),
            asset_context=data.get("asset_context", "").strip(),
            created_at=utc_now(),
        )
        self.repository.save_brief(brief)
        return brief

    def create_run(
        self,
        *,
        workspace_id: str,
        project_id: str,
        brief_version_id: str,
        model_preference: str,
        idempotency_key: str,
    ) -> tuple[Run, bool]:
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "brief_version_id": brief_version_id,
                    "model_preference": model_preference,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        existing = self.repository.find_run_by_idempotency_key(
            workspace_id, project_id, idempotency_key
        )
        if existing:
            if existing.request_fingerprint != fingerprint:
                raise IdempotencyConflictError("相同幂等键不能用于不同请求")
            return existing, False
        project = self.repository.get_project(project_id)
        if not project or project.workspace_id != workspace_id:
            raise ValueError("项目不属于指定工作空间")
        brief = self.repository.get_brief(brief_version_id)
        if not brief or brief.project_id != project_id:
            raise ValueError("参数版本不属于指定项目")
        run = Run.create(
            workspace_id=workspace_id,
            project_id=project_id,
            brief_version_id=brief_version_id,
            model_preference=model_preference,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
        try:
            self.repository.save_run(run)
            return run, True
        except RepositoryConflictError:
            existing = self.repository.find_run_by_idempotency_key(
                workspace_id, project_id, idempotency_key
            )
            if not existing:
                raise
            if existing.request_fingerprint != fingerprint:
                raise IdempotencyConflictError("相同幂等键不能用于不同请求")
            return existing, False

    def execute_run(self, run_id: str, *, worker_id: str = "inline-worker") -> Run:
        run = self.repository.get_run(run_id)
        if not run:
            raise LookupError("运行记录不存在")
        if run.status is RunStatus.PASSED:
            return run
        if run.status is RunStatus.CANCELLED:
            return run
        if run.status is RunStatus.FAILED:
            if run.attempt >= self.max_run_attempts:
                return run
            run = run.transition(RunStatus.RETRYING)
            self.repository.save_run(run)
        claimed = self.repository.claim_run(run.id, worker_id)
        if claimed is None:
            return self.repository.get_run(run.id) or run
        run = claimed
        claim_epoch = claimed.claim_epoch
        brief = self.repository.get_brief(run.brief_version_id)
        if not brief:
            raise LookupError("运行参数版本不存在")
        try:
            for status in (RunStatus.RUNNING, RunStatus.RETRIEVING, RunStatus.GENERATING):
                run = run.transition(status)
                self.repository.save_claimed_run(run, worker_id, claim_epoch)
                if not self.repository.heartbeat_run(run.id, worker_id, claim_epoch):
                    raise RepositoryConflictError("worker lost the run lease")
                run = self.repository.get_run(run.id) or run
            content_brief = ContentBrief(
                craft=brief.craft,
                story_seed=brief.story_seed,
                audience=brief.audience,
                platform=brief.platform,
                tone=brief.tone,
                goal=brief.goal,
                duration=brief.duration,
                aspect_ratio=brief.aspect_ratio,
                asset_context=brief.asset_context,
            )
            with _RunLeaseKeeper(
                self.repository, run.id, worker_id, claim_epoch
            ) as lease_keeper:
                generated, mode = generate_content_script_for_mode(
                    content_brief, run.model_preference
                )
                lease_keeper.ensure_owned()
            persisted = self.repository.get_run(run.id)
            if persisted and persisted.status is RunStatus.CANCELLED:
                return persisted
            run = run.transition(RunStatus.VALIDATING)
            self.repository.save_claimed_run(run, worker_id, claim_epoch)
            verification = verify_script(brief, generated)
            if not verification.passed:
                run = run.transition(
                    RunStatus.FAILED,
                    error_code="verification_failed",
                    error_message="; ".join(issue.message for issue in verification.issues),
                )
                self.repository.save_claimed_run(run, worker_id, claim_epoch)
                return run
            trace = generated.retrieval_trace
            evidence: dict[str, Any] = {
                "mode": mode,
                "retrieval": asdict(trace) if trace else {},
                "model": asdict(generated.model_evidence) if generated.model_evidence else {},
                "verification": verification_to_dict(verification),
            }
            script = ScriptVersion(
                id=new_id("script"),
                project_id=run.project_id,
                run_id=run.id,
                brief_version_id=run.brief_version_id,
                version=self.repository.next_script_version(run.project_id),
                payload=asdict(generated),
                evidence=evidence,
                created_at=utc_now(),
            )
            run = run.transition(RunStatus.PASSED)
            self.repository.complete_run_with_script(run, script, worker_id, claim_epoch)
            return run
        except Exception as exc:
            persisted = self.repository.get_run(run.id)
            if persisted and persisted.status is RunStatus.CANCELLED:
                return persisted
            if run.status not in {RunStatus.PASSED, RunStatus.FAILED, RunStatus.CANCELLED}:
                run = run.transition(
                    RunStatus.FAILED,
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                )
                self.repository.save_claimed_run(run, worker_id, claim_epoch)
            return run

    def cancel_run(self, run_id: str) -> Run:
        run = self.repository.get_run(run_id)
        if not run:
            raise LookupError("运行记录不存在")
        if run.status is RunStatus.CANCELLED:
            return run
        if run.status in {RunStatus.PASSED, RunStatus.FAILED}:
            raise RunNotCancellableError(f"终态运行不能取消：{run.status.value}")
        cancelled = self.repository.cancel_run(run_id)
        if cancelled:
            return cancelled
        current = self.repository.get_run(run_id)
        if current and current.status is RunStatus.CANCELLED:
            return current
        if current:
            raise RunNotCancellableError(f"运行状态已变化，不能取消：{current.status.value}")
        raise LookupError("运行记录不存在")

    def retry_failed_job(self, failed_job_id: str, workspace_id: str) -> Run:
        try:
            retrying = self.repository.retry_failed_job(
                failed_job_id,
                workspace_id,
                max_attempts=self.max_run_attempts,
            )
        except RepositoryConflictError as exc:
            raise FailedJobNotRetryableError("失败任务状态已变化") from exc
        if retrying:
            return retrying
        job = self.repository.get_failed_job(failed_job_id, workspace_id)
        if not job:
            raise LookupError("失败任务不存在")
        run = self.repository.get_run(job.run_id)
        if not run:
            raise LookupError("运行记录不存在")
        if job.resolved_at:
            raise FailedJobNotRetryableError("失败任务已处理")
        if run.status is not RunStatus.FAILED:
            raise FailedJobNotRetryableError(f"运行状态不能重试：{run.status.value}")
        if run.attempt >= self.max_run_attempts:
            raise FailedJobNotRetryableError("运行已达到最大尝试次数")
        raise FailedJobNotRetryableError("失败任务状态已变化")

    def resolve_failed_job(self, failed_job_id: str, workspace_id: str) -> FailedJob:
        job = self.repository.resolve_failed_job(failed_job_id, workspace_id)
        if not job:
            raise LookupError("失败任务不存在")
        return job
