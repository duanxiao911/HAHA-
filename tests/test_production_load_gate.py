from scripts.production_load_gate import Sample, evaluate, percentile, summarize


def test_nearest_rank_percentile_and_summary_are_deterministic() -> None:
    samples = [Sample(200, float(value)) for value in range(1, 101)]
    samples.append(Sample(503, 120, "HTTP 503"))

    summary = summarize(samples)

    assert percentile([1, 2, 3, 4], 95) == 4
    assert summary["requests"] == 101
    assert summary["failed"] == 1
    assert summary["status_counts"] == {"200": 100, "503": 1}
    assert summary["latency_ms"]["p95"] == 96.0  # type: ignore[index]


def test_threshold_evaluation_fails_closed_for_errors_or_tail_latency() -> None:
    summary = summarize([Sample(200, 20), Sample(500, 1200, "HTTP 500")])

    checks = evaluate(
        summary,
        max_error_ratio=0.01,
        max_p95_ms=500,
        max_p99_ms=1000,
    )

    assert checks == {
        "error_ratio": False,
        "p95_latency": False,
        "p99_latency": False,
    }
