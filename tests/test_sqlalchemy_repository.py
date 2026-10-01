from haha_core.repository import CreatorRepository
from haha_core.service import CreatorService
from haha_core.sqlalchemy_repository import SQLAlchemyCreatorRepository


def test_sqlalchemy_repository_runs_the_same_creator_contract() -> None:
    repository: CreatorRepository = SQLAlchemyCreatorRepository(
        "sqlite+pysqlite:///:memory:", create_schema=True
    )
    service = CreatorService(repository)
    project = service.create_project(title="数据库适配测试", workspace_id="ws_test")
    brief = service.create_brief(
        project.id,
        craft="中国剪纸",
        story_seed="剪刀形成纹样",
        audience="文化爱好者",
        platform="B站",
        tone="纪录片",
        goal="文化科普",
        duration="90秒",
        aspect_ratio="16:9",
        asset_context="",
    )
    run, created = service.create_run(
        workspace_id="ws_test",
        project_id=project.id,
        brief_version_id=brief.id,
        model_preference="本地演示",
        idempotency_key="sqlalchemy-contract-001",
    )
    assert created is True
    completed = service.execute_run(run.id)
    assert completed.status.value == "PASSED"
    assert repository.get_script_for_run(run.id) is not None
