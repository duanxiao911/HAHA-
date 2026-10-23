"""Application service coordinating immutable briefs, runs and script versions."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from threading import Event, Thread
from typing import Any

from haha_community.media_storage import FileSystemMediaStorage
from haha_core.domain import (
    BriefVersion,
    CreatorImageAsset,
    FailedJob,
    ImageGenerationRequest,
    Project,
    Run,
    RunStatus,
    ScriptRevision,
    ScriptVersion,
    new_id,
    utc_now,
)
from haha_core.repository import CreatorRepository, RepositoryConflictError
from haha_core.verifier import verification_to_dict, verify_script
from haha_media.image_assets import download_generated_image
from haha_media.model_router import get_model_router
from haha_media.script_writer import ContentBrief, generate_content_script_for_mode


class IdempotencyConflictError(ValueError):
    """The same scoped key was reused with a different request body."""


class RunNotCancellableError(ValueError):
    """A terminal Run cannot transition to CANCELLED."""


class FailedJobNotRetryableError(ValueError):
    """A failed job cannot consume another bounded retry attempt."""


class ScriptRevisionConflictError(ValueError):
    """The editor submitted against a stale immutable revision."""


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

    def create_image_run(
        self, *, workspace_id: str, source_run_id: str, prompt: str,
        negative_prompt: str, size: str, count: int, watermark: bool,
        reference_asset_ids: tuple[str, ...], idempotency_key: str, user_id: str,
    ) -> tuple[Run, bool]:
        source = self.repository.get_run(source_run_id)
        if not source or source.workspace_id != workspace_id or source.status is not RunStatus.PASSED:
            raise ValueError("来源脚本运行不存在或尚未通过")
        revision = self.repository.get_latest_script_revision(source_run_id)
        if not revision or revision.review_status != "reviewed":
            raise ValueError("来源脚本必须完成人工修订与复核")
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise ValueError("图片提示词不能为空")
        if size not in {"1K", "2K", "4K"} or count not in range(1, 5):
            raise ValueError("图片尺寸或数量不在允许范围内")
        if reference_asset_ids:
            raise ValueError("参考图与图片编辑尚未完成供应商账号实测，当前不可用")
        request_body = {
            "source_run_id": source_run_id, "prompt": clean_prompt,
            "negative_prompt": negative_prompt.strip(), "size": size,
            "count": count, "watermark": watermark, "reference_asset_ids": [],
        }
        fingerprint = hashlib.sha256(json.dumps(
            request_body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        existing = self.repository.find_run_by_idempotency_key(
            workspace_id, source.project_id, idempotency_key
        )
        if existing:
            if existing.request_fingerprint != fingerprint:
                raise IdempotencyConflictError("相同幂等键不能用于不同图片请求")
            return existing, False
        run = Run.create(
            workspace_id=workspace_id, project_id=source.project_id,
            brief_version_id=source.brief_version_id, model_preference="Seedream",
            idempotency_key=idempotency_key, request_fingerprint=fingerprint,
        )
        request = ImageGenerationRequest(
            run_id=run.id, project_id=run.project_id, source_run_id=source_run_id,
            prompt=clean_prompt, negative_prompt=negative_prompt.strip(), size=size,
            count=count, watermark=watermark, reference_asset_ids=(),
            created_by=user_id, created_at=utc_now(),
        )
        try:
            self.repository.save_image_run(run, request)
            return run, True
        except RepositoryConflictError:
            existing = self.repository.find_run_by_idempotency_key(
                workspace_id, source.project_id, idempotency_key
            )
            if not existing or existing.request_fingerprint != fingerprint:
                raise IdempotencyConflictError("图片请求发生并发冲突")
            return existing, False

    def execute_image_run(self, run_id: str, *, worker_id: str = "inline-image-worker") -> Run:
        run = self.repository.get_run(run_id)
        request = self.repository.get_image_request(run_id)
        if not run or not request:
            raise LookupError("图片运行记录不存在")
        if run.status in {RunStatus.PASSED, RunStatus.CANCELLED}:
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
        claim_epoch = run.claim_epoch
        storage = FileSystemMediaStorage(os.getenv("HAHA_CREATOR_MEDIA_ROOT", "data/creator-media"))
        committed: list[str] = []
        try:
            for target in (RunStatus.RUNNING, RunStatus.RETRIEVING, RunStatus.GENERATING):
                run = run.transition(target)
                self.repository.save_claimed_run(run, worker_id, claim_epoch)
                if not self.repository.heartbeat_run(run.id, worker_id, claim_epoch):
                    raise RepositoryConflictError("worker lost the run lease")
                run = self.repository.get_run(run.id) or run
            effective_prompt = request.prompt
            if request.negative_prompt:
                effective_prompt += f"\n画面中避免出现：{request.negative_prompt}"
            with _RunLeaseKeeper(self.repository, run.id, worker_id, claim_epoch) as lease:
                result = get_model_router().generate_image(
                    effective_prompt, size=request.size, count=request.count,
                    watermark=request.watermark,
                )
                validated = [download_generated_image(url) for url in result.images]
                lease.ensure_owned()
            if len(validated) != request.count:
                raise ValueError("模型返回图片数量与请求不一致")
            run = run.transition(RunStatus.VALIDATING)
            self.repository.save_claimed_run(run, worker_id, claim_epoch)
            assets: list[CreatorImageAsset] = []
            for index, image in enumerate(validated, start=1):
                asset_id = new_id("image")
                partition = hashlib.sha256(run.workspace_id.encode()).hexdigest()[:16]
                storage_key = f"{partition}/{asset_id}{image.extension}"
                staged = storage.create_staging_path()
                try:
                    staged.write_bytes(image.data)
                    storage.commit(staged, storage_key)
                    committed.append(storage_key)
                finally:
                    storage.discard(staged)
                assets.append(CreatorImageAsset(
                    id=asset_id, workspace_id=run.workspace_id, project_id=run.project_id,
                    run_id=run.id, version=index,
                    mime_type=image.mime_type, byte_size=len(image.data), width=image.width,
                    height=image.height, sha256=image.sha256, storage_key=storage_key,
                    source_url_host=image.source_host, evidence=asdict(result.evidence),
                    created_at=utc_now(),
                ))
            run = run.transition(RunStatus.PASSED)
            self.repository.complete_run_with_images(run, assets, worker_id, claim_epoch)
            return run
        except Exception as exc:
            for storage_key in committed:
                storage.delete(storage_key)
            persisted = self.repository.get_run(run.id)
            if persisted and persisted.status is RunStatus.CANCELLED:
                return persisted
            if run.status not in {RunStatus.PASSED, RunStatus.FAILED, RunStatus.CANCELLED}:
                run = run.transition(RunStatus.FAILED, error_code=type(exc).__name__, error_message=str(exc))
                self.repository.save_claimed_run(run, worker_id, claim_epoch)
            return run
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

    def create_script_revision(
        self, run_id: str, *, payload: dict[str, Any], expected_version: int, user_id: str
    ) -> ScriptRevision:
        run = self.repository.get_run(run_id)
        if not run or run.status is not RunStatus.PASSED:
            raise LookupError("只有已通过验收的运行可以修订")
        base = self.repository.get_script_for_run(run_id)
        if not base:
            raise LookupError("原始生成版本不存在")
        latest = self.repository.get_latest_script_revision(run_id)
        current_version = latest.version if latest else 0
        if expected_version != current_version:
            raise ScriptRevisionConflictError("脚本已产生新版本，请刷新后继续编辑")
        allowed = {"title", "hook", "voiceover", "shots", "caption", "tags"}
        if set(payload) != allowed:
            raise ValueError("修订内容字段不完整或包含未知字段")
        for field in ("title", "hook", "caption"):
            if not isinstance(payload[field], str) or not str(payload[field]).strip():
                raise ValueError(f"{field} 不能为空")
        for field in ("voiceover", "shots", "tags"):
            value = payload[field]
            if not isinstance(value, list) or not value or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                raise ValueError(f"{field} 必须是非空文本列表")
        serialized = json.dumps(payload, ensure_ascii=False)
        if len(serialized.encode("utf-8")) > 128_000:
            raise ValueError("修订内容超过 128KB 限制")
        now = utc_now()
        revision = ScriptRevision(
            id=new_id("revision"), project_id=run.project_id, run_id=run.id,
            base_script_id=base.id, version=current_version + 1,
            payload=payload, review_status="draft", review_note="",
            created_by=user_id, created_at=now, updated_at=now,
        )
        try:
            self.repository.save_script_revision(revision)
        except RepositoryConflictError as exc:
            raise ScriptRevisionConflictError("脚本已产生新版本，请刷新后继续编辑") from exc
        return revision

    def review_script_revision(
        self, run_id: str, *, expected_version: int, note: str, user_id: str
    ) -> ScriptRevision:
        latest = self.repository.get_latest_script_revision(run_id)
        if not latest:
            raise LookupError("尚无可复核的人工修订版本")
        if latest.version != expected_version:
            raise ScriptRevisionConflictError("脚本已产生新版本，请刷新后重新复核")
        if latest.review_status == "reviewed":
            return latest
        now = utc_now()
        reviewed = ScriptRevision(
            id=new_id("revision"), project_id=latest.project_id, run_id=latest.run_id,
            base_script_id=latest.base_script_id, version=latest.version + 1,
            payload=latest.payload, review_status="reviewed", review_note=note.strip(),
            created_by=user_id, created_at=now, updated_at=now,
        )
        try:
            self.repository.save_script_revision(reviewed)
        except RepositoryConflictError as exc:
            raise ScriptRevisionConflictError("脚本已产生新版本，请刷新后重新复核") from exc
        return reviewed

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
