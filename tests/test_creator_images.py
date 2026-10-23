from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from haha_core.domain import RunStatus
from haha_core.repository import SQLiteCreatorRepository
from haha_core.service import CreatorService
from haha_media.image_assets import ImageAssetError, validate_image_bytes


def _reviewed_source(service: CreatorService) -> str:
    project = service.create_project(title="图片创作", workspace_id="ws_image")
    brief = service.create_brief(
        project.id, craft="中国剪纸", story_seed="剪刀落下形成纹样",
        audience="传统文化初学者", platform="小红书", tone="纪录片",
        goal="文化科普", duration="60秒", aspect_ratio="3:4", asset_context="",
    )
    run, _ = service.create_run(
        workspace_id="ws_image", project_id=project.id, brief_version_id=brief.id,
        model_preference="本地演示", idempotency_key="source-script-run",
    )
    assert service.execute_run(run.id).status is RunStatus.PASSED
    script = service.repository.get_script_for_run(run.id)
    assert script is not None
    payload = {key: script.payload[key] for key in ("title", "hook", "voiceover", "shots", "caption", "tags")}
    revision = service.create_script_revision(run.id, payload=payload, expected_version=0, user_id="user_image")
    service.review_script_revision(run.id, expected_version=revision.version, note="人工复核", user_id="user_image")
    return run.id


def test_image_run_is_durable_idempotent_and_reference_editing_is_blocked() -> None:
    service = CreatorService(SQLiteCreatorRepository(":memory:"))
    source_run_id = _reviewed_source(service)
    run, created = service.create_image_run(
        workspace_id="ws_image", source_run_id=source_run_id, prompt="红纸剪刻纹样特写",
        negative_prompt="文字、水印", size="2K", count=1, watermark=True,
        reference_asset_ids=(), idempotency_key="image-run-0001", user_id="user_image",
    )
    replay, replay_created = service.create_image_run(
        workspace_id="ws_image", source_run_id=source_run_id, prompt="红纸剪刻纹样特写",
        negative_prompt="文字、水印", size="2K", count=1, watermark=True,
        reference_asset_ids=(), idempotency_key="image-run-0001", user_id="user_image",
    )
    assert created is True
    assert replay_created is False
    assert replay.id == run.id
    assert service.repository.get_image_request(run.id) is not None
    with pytest.raises(ValueError, match="参考图"):
        service.create_image_run(
            workspace_id="ws_image", source_run_id=source_run_id, prompt="编辑图片",
            negative_prompt="", size="1K", count=1, watermark=True,
            reference_asset_ids=("image_unknown",), idempotency_key="image-edit-0001",
            user_id="user_image",
        )


def test_image_execution_fails_closed_without_real_provider_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("LAS_API_KEY", raising=False)
    service = CreatorService(SQLiteCreatorRepository(":memory:"))
    source_run_id = _reviewed_source(service)
    run, _ = service.create_image_run(
        workspace_id="ws_image", source_run_id=source_run_id, prompt="红纸剪刻纹样特写",
        negative_prompt="", size="1K", count=1, watermark=True,
        reference_asset_ids=(), idempotency_key="image-no-key", user_id="user_image",
    )
    completed = service.execute_image_run(run.id)
    assert completed.status is RunStatus.FAILED
    assert completed.error_code == "ModelCallError"
    assert "ARK_API_KEY" in completed.error_message
    assert service.repository.list_image_assets(run.project_id) == []


def test_image_bytes_require_full_decode_and_hash() -> None:
    buffer = BytesIO()
    Image.new("RGB", (96, 64), color=(180, 20, 30)).save(buffer, format="PNG")
    validated = validate_image_bytes(buffer.getvalue(), source_host="example.volces.com")
    assert validated.mime_type == "image/png"
    assert (validated.width, validated.height) == (96, 64)
    assert len(validated.sha256) == 64
    with pytest.raises(ImageAssetError, match="解码"):
        validate_image_bytes(buffer.getvalue()[:32], source_host="example.volces.com")
