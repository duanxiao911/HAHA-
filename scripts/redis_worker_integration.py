"""Real Redis/Dramatiq/PostgreSQL worker integration check."""

from __future__ import annotations

import json
import os
import time
from uuid import uuid4

from sqlalchemy import func, select

from haha_core.service import CreatorService
from haha_core.sqlalchemy_repository import SQLAlchemyCreatorRepository, script_versions
from haha_worker.tasks import execute_creator_run


def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    repository = SQLAlchemyCreatorRepository(database_url)
    service = CreatorService(repository)
    suffix = uuid4().hex
    workspace_id = f"worker-ws-{suffix}"
    user_id = f"worker-user-{suffix}"
    repository.ensure_identity(user_id, workspace_id, role="owner")
    project = service.create_project(title="Worker integration", workspace_id=workspace_id)
    brief = service.create_brief(
        project.id,
        craft="中国剪纸",
        story_seed="剪刀落下形成纹样",
        audience="文化初学者",
        platform="B站",
        tone="人物纪实",
        goal="文化科普",
        duration="90秒",
        aspect_ratio="16:9",
        asset_context="real worker integration",
    )
    run, created = service.create_run(
        workspace_id=workspace_id,
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="本地演示",
        idempotency_key=f"worker-{suffix}",
    )
    assert created
    execute_creator_run.send(run.id)
    execute_creator_run.send(run.id)

    deadline = time.monotonic() + 30
    completed = run
    while time.monotonic() < deadline:
        completed = repository.get_run(run.id) or completed
        if completed.status.value in {"PASSED", "FAILED"}:
            break
        time.sleep(0.25)
    script = repository.get_script_for_run(run.id)
    with repository.engine.connect() as connection:
        script_count = connection.scalar(
            select(func.count()).select_from(script_versions).where(
                script_versions.c.run_id == run.id
            )
        )
    result = {
        "run_id": run.id,
        "status": completed.status.value,
        "claimed_by": completed.claimed_by,
        "script_count": int(script_count or 0),
        "platform": script.payload["judgment"][3][1] if script else None,
        "spec": script.payload["judgment"][4][1] if script else None,
    }
    print(json.dumps(result, ensure_ascii=False))
    assert result["status"] == "PASSED"
    assert result["script_count"] == 1
    assert result["platform"] == "B站"
    assert result["spec"] == "90秒 · 16:9"


if __name__ == "__main__":
    main()
