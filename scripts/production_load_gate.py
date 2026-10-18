"""Dependency-free HTTP capacity smoke with machine-enforced latency/error gates."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Sample:
    status: int
    latency_ms: float
    error: str = ""


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil((percentile_value / 100) * len(ordered)) - 1)
    return ordered[index]


def summarize(samples: list[Sample]) -> dict[str, object]:
    latencies = [sample.latency_ms for sample in samples]
    failures = [sample for sample in samples if sample.status != 200 or sample.error]
    total = len(samples)
    return {
        "requests": total,
        "succeeded": total - len(failures),
        "failed": len(failures),
        "error_ratio": round(len(failures) / total, 6) if total else 1.0,
        "latency_ms": {
            "min": round(min(latencies), 3) if latencies else 0.0,
            "p50": round(percentile(latencies, 50), 3),
            "p95": round(percentile(latencies, 95), 3),
            "p99": round(percentile(latencies, 99), 3),
            "max": round(max(latencies), 3) if latencies else 0.0,
        },
        "status_counts": {
            str(status): sum(1 for sample in samples if sample.status == status)
            for status in sorted({sample.status for sample in samples})
        },
    }


def evaluate(
    summary: dict[str, object], *, max_error_ratio: float, max_p95_ms: float,
    max_p99_ms: float,
) -> dict[str, bool]:
    latency = summary["latency_ms"]
    assert isinstance(latency, dict)
    return {
        "error_ratio": float(summary["error_ratio"]) <= max_error_ratio,
        "p95_latency": float(latency["p95"]) <= max_p95_ms,
        "p99_latency": float(latency["p99"]) <= max_p99_ms,
    }


def request_once(url: str, timeout: float, bearer_token: str) -> Sample:
    headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
    request = urllib.request.Request(url, headers=headers, method="GET")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            status = response.status
            error = ""
    except urllib.error.HTTPError as exc:
        exc.read()
        status = exc.code
        error = f"HTTP {exc.code}"
    except (OSError, TimeoutError) as exc:
        status = 0
        error = type(exc).__name__
    return Sample(status, (time.perf_counter() - started) * 1000, error)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/ready")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--max-error-ratio", type=float, default=0.01)
    parser.add_argument("--max-p95-ms", type=float, default=500)
    parser.add_argument("--max-p99-ms", type=float, default=1000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1 or args.warmup < 0:
        parser.error("requests/concurrency must be positive and warmup cannot be negative")
    token = os.getenv("HAHA_LOAD_GATE_BEARER_TOKEN", "")
    for _ in range(args.warmup):
        request_once(args.url, args.timeout, token)
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        samples = list(
            pool.map(
                lambda _: request_once(args.url, args.timeout, token),
                range(args.requests),
            )
        )
    summary = summarize(samples)
    checks = evaluate(
        summary,
        max_error_ratio=args.max_error_ratio,
        max_p95_ms=args.max_p95_ms,
        max_p99_ms=args.max_p99_ms,
    )
    result = {
        "status": "passed" if all(checks.values()) else "failed",
        "target": args.url,
        "concurrency": args.concurrency,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "thresholds": {
            "max_error_ratio": args.max_error_ratio,
            "max_p95_ms": args.max_p95_ms,
            "max_p99_ms": args.max_p99_ms,
        },
        "checks": checks,
        "summary": summary,
        "failed_samples": [asdict(sample) for sample in samples if sample.error][:10],
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
