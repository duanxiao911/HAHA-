"""Dramatiq actors. Actors reconstruct dependencies for process-safe execution."""

from __future__ import annotations

import os
import socket

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from haha_api.observability import log_event, request_id_context
from haha_core.bootstrap import build_repository
from haha_core.service import CreatorService

redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
dramatiq.set_broker(RedisBroker(url=redis_url))


@dramatiq.actor(
    actor_name="execute_creator_run",
    max_retries=3,
    min_backoff=5_000,
    max_backoff=60_000,
    time_limit=360_000,
)
def execute_creator_run(run_id: str, request_id: str = "") -> None:
    token = request_id_context.set(request_id)
    try:
        _execute_creator_run(run_id)
    finally:
        request_id_context.reset(token)


def _execute_creator_run(run_id: str) -> None:
    service = CreatorService(build_repository())
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    log_event(
        "worker.run.started",
        component="worker",
        run_id=run_id,
        worker_id=worker_id,
    )
    run = service.execute_run(run_id, worker_id=worker_id)
    retryable = run.error_code in {
        "TimeoutError",
        "URLError",
        "ModelCallError",
    }
    if run.status.value == "FAILED" and retryable and run.attempt < service.max_run_attempts:
        log_event(
            "worker.run.retry_scheduled",
            component="worker",
            run_id=run.id,
            worker_id=worker_id,
            attempt=run.attempt,
            error_code=run.error_code,
        )
        raise RuntimeError(f"transient creator run failure: {run.error_code}")
    if run.status.value == "FAILED":
        service.repository.record_failed_job(run.id, run.error_code or "run_failed")
        log_event(
            "worker.run.failed",
            component="worker",
            run_id=run.id,
            worker_id=worker_id,
            attempt=run.attempt,
            error_code=run.error_code,
        )
        return
    if run.status.value != "PASSED":
        log_event(
            "worker.run.skipped",
            component="worker",
            run_id=run.id,
            worker_id=worker_id,
            attempt=run.attempt,
            status=run.status.value,
        )
        return
    log_event(
        "worker.run.completed",
        component="worker",
        run_id=run.id,
        worker_id=worker_id,
        attempt=run.attempt,
        status=run.status.value,
    )
