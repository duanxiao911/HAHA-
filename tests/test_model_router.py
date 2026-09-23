import pytest

from haha_media.model_router import ModelCallError, ModelRouter


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
