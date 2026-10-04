"""Run a deliberately small, budget-capped live-provider quality gate."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from haha_media.model_router import ModelCallError, ModelRouter, TextModelResult
from haha_media.script_writer import ContentBrief, generate_content_script_with_model

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals" / "golden_dataset.json"
REPORT = ROOT / "artifacts" / "evals" / "phase-b-live-ai-eval.json"

MODEL_SEQUENCE = ("deepseek-flash", "deepseek-v4-pro")
PEAK_PRICE_USD_PER_MILLION = {
    "deepseek-flash": {"input": 0.30, "output": 1.20},
    "deepseek-v4-pro": {"input": 1.32, "output": 3.96},
}


class BudgetRouter(ModelRouter):
    """Apply a hard output-token ceiling without changing production routing."""

    def __init__(self, output_token_cap: int) -> None:
        super().__init__()
        self.output_token_cap = output_token_cap

    def generate_json(
        self,
        task: str,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> TextModelResult:
        return super().generate_json(
            task,  # type: ignore[arg-type]
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=min(max_tokens, self.output_token_cap),
            model=model,
        )


def _positive_bounded_int(name: str, default: int, maximum: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def _estimate_peak_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price = PEAK_PRICE_USD_PER_MILLION[model]
    return round(
        (input_tokens * price["input"] + output_tokens * price["output"])
        / 1_000_000,
        8,
    )


def _evaluate_case(case: dict[str, Any], model: str, router: BudgetRouter) -> dict[str, Any]:
    brief = ContentBrief(
        craft=case["craft"],
        story_seed=case["story_seed"],
        audience=case["audience"],
        platform=case["platform"],
        tone=case["tone"],
        duration=case["duration"],
        aspect_ratio=case["aspect_ratio"],
    )
    try:
        script = generate_content_script_with_model(brief, router=router, model=model)
        judgment = dict(script.judgment)
        checks = {
            "platform": judgment.get("推荐平台") == brief.platform,
            "duration_and_ratio": judgment.get("推荐规格")
            == f"{brief.duration} · {brief.aspect_ratio}",
            "tone": judgment.get("表达气质") == brief.tone,
            "required_fields": all(
                (
                    script.title,
                    script.hook,
                    script.voiceover,
                    script.shots,
                    script.caption,
                    script.tags,
                )
            ),
            "retrieval_trace": bool(
                script.retrieval_trace
                and script.retrieval_trace.creative_chunks_used
                and script.retrieval_trace.operation_chunks_used
            ),
            "fact_boundary": bool(script.fact_sources) == bool(
                case.get("expected_fact_name")
            ),
        }
        evidence = script.model_evidence
        if evidence is None:
            raise RuntimeError("live model result did not include call evidence")
        peak_cost = _estimate_peak_cost(
            model, evidence.input_tokens, evidence.output_tokens
        )
        return {
            "id": case["id"],
            "model": model,
            "status": "passed" if all(checks.values()) else "failed",
            "checks": checks,
            "evidence": asdict(evidence),
            "estimated_peak_cost_usd": peak_cost,
        }
    except ModelCallError as exc:
        evidence = asdict(exc.evidence) if exc.evidence else None
        return {
            "id": case["id"],
            "model": model,
            "status": "failed",
            "checks": {},
            "evidence": evidence,
            "error": str(exc),
            "estimated_peak_cost_usd": 0.0,
        }


def main() -> None:
    max_cases = _positive_bounded_int("HAHA_LIVE_EVAL_MAX_CASES", 2, 2)
    output_cap = _positive_bounded_int("HAHA_LIVE_EVAL_OUTPUT_TOKEN_CAP", 900, 1200)
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = dataset["cases"][:max_cases]
    router = BudgetRouter(output_cap)
    if not router.status().text_ready:
        raise RuntimeError("DEEPSEEK_API_KEY is required for the live evaluation")
    results = [
        _evaluate_case(case, MODEL_SEQUENCE[index], router)
        for index, case in enumerate(cases)
    ]
    total_input = sum(
        int((result.get("evidence") or {}).get("input_tokens", 0))
        for result in results
    )
    total_output = sum(
        int((result.get("evidence") or {}).get("output_tokens", 0))
        for result in results
    )
    report = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "mode": "live-provider-budget-capped",
        "budget": {
            "maximum_calls": 2,
            "actual_calls": len(results),
            "output_token_cap_per_call": output_cap,
            "pricing_basis": "conservative peak, cache-miss input",
        },
        "summary": {
            "cases": len(results),
            "passed": sum(result["status"] == "passed" for result in results),
            "gate_passed": all(result["status"] == "passed" for result in results),
            "input_tokens": total_input,
            "output_tokens": total_output,
            "estimated_peak_cost_usd": round(
                sum(result["estimated_peak_cost_usd"] for result in results), 8
            ),
        },
        "results": results,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    if not report["summary"]["gate_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
