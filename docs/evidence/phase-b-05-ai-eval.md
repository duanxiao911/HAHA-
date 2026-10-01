# Phase B-05 — AI evaluation gate

Date: 2026-10-01

## Dataset and scoring

- Versioned 10-case Golden Dataset across craft, performing art, oral tradition and traditional music.
- Platform coverage: B站、小红书、抖音、视频号.
- Duration and aspect-ratio variants.
- Four weighted checks per case: parameter following, required output fields, retrieval trace and fact boundary.
- A deliberately unknown project verifies fail-closed fact retrieval instead of attaching a plausible but unrelated record.
- Per-case threshold: 0.90; required dataset pass rate: 1.00.

## Result

```json
{"cases": 10, "passed": 10, "pass_rate": 1.0, "gate_passed": true}
```

Regression tests covering the dataset and affected knowledge/generation code:

```text
18 passed
```

The deterministic offline gate is included in CI. It verifies HAHA's generation pipeline and evidence
boundary without consuming an external model API. A live-provider quality/cost/latency comparison remains
separate and requires an explicit staging API credential; no live-provider score is claimed here.

Artifact: `artifacts/evals/phase-b-ai-eval.json`
