from haha_core import bootstrap


def test_enqueue_run_is_disabled_without_redis(monkeypatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert bootstrap.enqueue_run("run_test") is False
