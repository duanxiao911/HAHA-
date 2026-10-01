import pytest

from haha_media.model_router import (
    CallEvidence,
    ModelCallError,
    ModelRouter,
    TextModelResult,
)
from haha_media.script_writer import ContentBrief, generate_content_script_for_mode


def test_router_reports_provider_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
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
    assert ready_router.resolve_text_mode("DeepSeek-V4.1-Flash") == "deepseek"
    assert ready_router.resolve_text_mode("DeepSeek-V4-Pro") == "deepseek"
    assert ready_router.resolve_text_model("DeepSeek-V4.1-Flash") == "deepseek-flash"
    assert ready_router.resolve_text_model("DeepSeek-V4-Pro") == "deepseek-v4-pro"


def test_script_generation_uses_selected_route(monkeypatch: pytest.MonkeyPatch) -> None:
    import haha_media.script_writer as script_writer

    brief = ContentBrief("竹编", "竹篾弯折", "新手", "小红书", "克制")
    router = ModelRouter()
    calls: list[str] = []

    def fake_model_generation(
        _brief: ContentBrief, *, router: ModelRouter, model: str | None = None
    ) -> object:
        calls.append(str(model))
        return script_writer.generate_content_script(_brief)

    monkeypatch.setattr(script_writer, "generate_content_script_with_model", fake_model_generation)
    local_script, local_mode = generate_content_script_for_mode(brief, "本地演示", router)
    assert local_mode == "local"
    assert local_script.model_evidence is None
    assert local_script.retrieval_trace is not None
    assert local_script.retrieval_trace.model == "local-demo-generator"
    assert calls == []

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    router = ModelRouter()
    api_script, api_mode = generate_content_script_for_mode(
        brief, "DeepSeek-V4-Pro", router
    )
    assert api_mode == "api"
    assert api_script.model_evidence is None
    assert calls == ["deepseek-v4-pro"]


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


def test_api_run_records_provider_evidence_and_knowledge_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brief = ContentBrief("竹编", "竹篾弯折", "新手", "小红书", "克制")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    router = ModelRouter()
    evidence = CallEvidence(
        "deepseek", "deepseek-test-model", "request-42", 321, 120, 80
    )

    def fake_generate_json(*_args: object, **_kwargs: object) -> TextModelResult:
        return TextModelResult(
            {
                "title": "竹编标题",
                "hook": "竹篾如何弯折？",
                "voiceover": ["旁白一", "旁白二", "旁白三"],
                "shots": ["镜头一", "镜头二", "镜头三"],
                "caption": "发布说明",
                "tags": ["#竹编", "#非遗"],
            },
            evidence,
        )

    monkeypatch.setattr(router, "generate_json", fake_generate_json)
    script, mode = generate_content_script_for_mode(brief, "DeepSeek", router)

    assert mode == "api"
    assert script.model_evidence == evidence
    assert script.retrieval_trace is not None
    assert script.retrieval_trace.model == "deepseek-test-model"


def test_api_output_cannot_override_submitted_delivery_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brief = ContentBrief(
        "中国剪纸", "剪刀沿着红纸移动", "传统文化爱好者", "B站", "人物纪实", duration="30秒", aspect_ratio="16:9"
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    router = ModelRouter()
    evidence = CallEvidence("deepseek", "deepseek-test-model", "request-wrong-output", 123)

    def fake_generate_json(*_args: object, **_kwargs: object) -> TextModelResult:
        return TextModelResult(
            {
                "title": "小红书45秒剪纸",
                "hook": "小红书用户请看这45秒",
                "voiceover": ["小红书旁白45秒", "旁白二", "旁白三"],
                "shots": ["0–3秒", "3–40秒", "40–45秒"],
                "caption": "小红书45秒发布说明",
                "tags": ["#小红书", "#45秒"],
            },
            evidence,
        )

    monkeypatch.setattr(router, "generate_json", fake_generate_json)
    script, mode = generate_content_script_for_mode(brief, "DeepSeek", router)

    assert mode == "api"
    assert "小红书" not in " ".join((script.title, script.hook, *script.voiceover, script.caption, *script.tags))
    assert "45秒" not in " ".join((script.title, script.hook, *script.voiceover, script.caption, *script.tags))
    assert script.shots[-1].startswith("26–30 秒")
    assert ("推荐平台", "B站") in script.judgment
    assert ("表达气质", "人物纪实") in script.judgment


def test_failed_api_run_keeps_provider_and_knowledge_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brief = ContentBrief("竹编", "竹篾弯折", "新手", "小红书", "克制")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    router = ModelRouter()
    evidence = CallEvidence("deepseek", "deepseek-test-model", "request-fail", 210, status="failed")

    def fail_generate_json(*_args: object, **_kwargs: object) -> TextModelResult:
        raise ModelCallError(
            "模型服务返回 HTTP 503。",
            detail="HTTP 503: provider unavailable",
            evidence=evidence,
        )

    monkeypatch.setattr(router, "generate_json", fail_generate_json)
    with pytest.raises(ModelCallError, match="HTTP 503") as caught:
        generate_content_script_for_mode(brief, "DeepSeek", router)

    assert caught.value.detail == "HTTP 503: provider unavailable"
    assert caught.value.evidence == evidence
    assert caught.value.retrieval_trace is not None
    assert caught.value.retrieval_trace.model == "local-demo-generator"


def test_incomplete_api_response_is_failed_not_filled_from_local_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brief = ContentBrief("竹编", "竹篾弯折", "新手", "小红书", "克制")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    router = ModelRouter()

    def incomplete_response(*_args: object, **_kwargs: object) -> TextModelResult:
        return TextModelResult(
            {"title": "API title only"},
            CallEvidence("deepseek", "deepseek-test-model", "request-partial", 100),
        )

    monkeypatch.setattr(router, "generate_json", incomplete_response)
    with pytest.raises(ModelCallError, match="缺少必需字段") as caught:
        generate_content_script_for_mode(brief, "DeepSeek", router)

    assert caught.value.evidence is not None
    assert caught.value.evidence.status == "failed"
    assert caught.value.retrieval_trace is not None


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
