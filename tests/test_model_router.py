import pytest

from haha_media.model_router import ModelCallError, ModelRouter
from haha_media.script_writer import ContentBrief, generate_content_script_for_mode


def test_router_reports_provider_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("LAS_API_KEY", raising=False)

    status = ModelRouter().status()

    assert status.text_ready is False
    assert status.image_ready is False
    assert status.text_model == "deepseek-flash"
    assert status.image_model == "doubao-seedream-4.5"


def test_router_rejects_calls_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("LAS_API_KEY", raising=False)
    router = ModelRouter()

    with pytest.raises(ModelCallError, match="DEEPSEEK_API_KEY"):
        router.generate_json(
            "creation_judgement", system_prompt="请输出 json", user_prompt="竹编"
        )
    with pytest.raises(ModelCallError, match="ARK_API_KEY"):
        router.generate_image("竹编手部特写")


def test_text_model_preference_resolves_to_actual_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    router = ModelRouter()

    assert router.resolve_text_mode("自动选择") == "local"
    assert router.resolve_text_mode("本地演示") == "local"
    with pytest.raises(ModelCallError, match="DEEPSEEK_API_KEY"):
        router.resolve_text_mode("DeepSeek")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    ready_router = ModelRouter()
    assert ready_router.resolve_text_mode("自动选择") == "deepseek"
    assert ready_router.resolve_text_mode("DeepSeek") == "deepseek"


def test_script_generation_uses_selected_route(monkeypatch: pytest.MonkeyPatch) -> None:
    import haha_media.script_writer as script_writer

    brief = ContentBrief("竹编", "竹篾弯折", "新手", "小红书", "克制")
    router = ModelRouter()
    calls: list[str] = []

    def fake_model_generation(_brief: ContentBrief, *, router: ModelRouter) -> object:
        calls.append("deepseek")
        return script_writer.generate_content_script(_brief)

    monkeypatch.setattr(script_writer, "generate_content_script_with_model", fake_model_generation)
    local_script, local_mode = generate_content_script_for_mode(brief, "本地演示", router)
    assert local_mode == "local"
    assert local_script.model_evidence is None
    assert calls == []

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    router = ModelRouter()
    api_script, api_mode = generate_content_script_for_mode(brief, "DeepSeek", router)
    assert api_mode == "api"
    assert api_script.model_evidence is None
    assert calls == ["deepseek"]


def test_failed_deepseek_selection_does_not_fall_back_to_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import haha_media.script_writer as script_writer

    brief = ContentBrief("竹编", "竹篾弯折", "新手", "小红书", "克制")
    router = ModelRouter()

    def fail_model_generation(*_args: object, **_kwargs: object) -> object:
        raise ModelCallError("模型服务连接失败")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    router = ModelRouter()
    monkeypatch.setattr(script_writer, "generate_content_script_with_model", fail_model_generation)
    monkeypatch.setattr(
        script_writer,
        "generate_content_script",
        lambda _brief: pytest.fail("API 失败后不应回退到本地生成"),
    )
    with pytest.raises(ModelCallError, match="模型服务连接失败"):
        generate_content_script_for_mode(brief, "DeepSeek", router)


def test_router_normalizes_text_and_image_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    monkeypatch.setenv("ARK_API_KEY", "test-ark")
    router = ModelRouter()
    responses = iter(
        (
            (
                {
                    "id": "text-run-1",
                    "model": "deepseek-flash",
                    "choices": [{"message": {"content": '{"direction":"手部工艺"}'}}],
                    "usage": {"prompt_tokens": 120, "completion_tokens": 80},
                },
                {},
                320,
            ),
            (
                {
                    "id": "image-run-1",
                    "model": "doubao-seedream-4.5",
                    "data": [{"url": "https://example.invalid/image.png"}],
                    "usage": {"output_tokens": 100},
                },
                {},
                850,
            ),
        )
    )

    def fake_post(*_args: object, **_kwargs: object):
        return next(responses)

    monkeypatch.setattr(router, "_post_json", fake_post)
    text = router.generate_json(
        "creation_judgement", system_prompt="请输出 json", user_prompt="竹编"
    )
    image = router.generate_image("竹编手部特写")

    assert text.data["direction"] == "手部工艺"
    assert text.evidence.request_id == "text-run-1"
    assert text.evidence.input_tokens == 120
    assert image.images == ("https://example.invalid/image.png",)
    assert image.evidence.provider == "volcengine"
