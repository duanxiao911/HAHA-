# Phase B-05 — AI evaluation gate

Date: 2026-10-01

## Dataset and scoring

- Versioned 10-case Golden Dataset across craft, performing art, oral tradition and traditional music.
- Platform coverage: B站、小红书、抖音、视频号.
- Duration and aspect-ratio variants.
- Four weighted checks per case: parameter following, required output fields, retrieval trace and fact boundary.
- A deliberately unknown project verifies fail-closed fact retrieval instead of attaching a plausible but unrelated record.
- Per-case threshold: 0.90; required dataset pass rate: 1.00.

## Offline deterministic result

```json
{"cases": 10, "passed": 10, "pass_rate": 1.0, "gate_passed": true}
```

Regression tests covering the dataset and affected knowledge/generation code:

```text
18 passed
```

The deterministic offline gate is included in CI. It verifies HAHA's generation pipeline and evidence
boundary without consuming an external model API.

Artifact: `artifacts/evals/phase-b-ai-eval.json`

## Budget-capped live-provider result

The live gate made exactly two calls: one `deepseek-flash` case and one `deepseek-v4-pro` case. Each call
had a hard 900 output-token ceiling. No credential or generated body is written to the report.

```json
{
  "cases": 2,
  "passed": 2,
  "gate_passed": true,
  "input_tokens": 2230,
  "output_tokens": 1067,
  "estimated_peak_cost_usd": 0.00424446
}
```

| Case | Model | Latency | Input | Output | Result |
|---|---|---:|---:|---:|---|
| paper-cutting-bilibili | deepseek-flash | 4,295 ms | 1,111 | 649 | PASS |
| suzhou-embroidery-xhs | deepseek-v4-pro | 6,253 ms | 1,119 | 418 | PASS |

Cost uses the conservative peak, cache-miss prices in the
[DeepSeek pricing table](https://api-docs.deepseek.com/quick_start/pricing/) on 2026-10-01. It is an
estimate rather than a billing statement. Artifact: `artifacts/evals/phase-b-live-ai-eval.json`.
