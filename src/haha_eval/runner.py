"""Deterministic golden-dataset evaluation with fail-closed quality gates."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from haha_core.repository import SQLiteCreatorRepository
from haha_core.service import CreatorService
from haha_core.verifier import verify_script
from haha_media.script_writer import ContentBrief, generate_content_script


def load_dataset(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or not payload.get("cases"):
        raise ValueError("Unsupported or empty golden dataset")
    return payload


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    repository = SQLiteCreatorRepository(":memory:")
    service = CreatorService(repository)
    project = service.create_project(title=case["id"], workspace_id="eval")
    brief = service.create_brief(
        project.id,
        craft=case["craft"],
        story_seed=case["story_seed"],
        audience=case["audience"],
        platform=case["platform"],
        tone=case["tone"],
        goal="文化科普",
        duration=case["duration"],
        aspect_ratio=case["aspect_ratio"],
        asset_context="",
    )
    script = generate_content_script(
        ContentBrief(
            craft=brief.craft,
            story_seed=brief.story_seed,
            audience=brief.audience,
            platform=brief.platform,
            tone=brief.tone,
            goal=brief.goal,
            duration=brief.duration,
            aspect_ratio=brief.aspect_ratio,
        )
    )
    verification = verify_script(brief, script)
    expected_fact = case.get("expected_fact_name")
    retrieved_names = [name for _, name, _ in script.fact_sources]
    evidence_ok = (
        expected_fact in retrieved_names
        if expected_fact
        else not script.fact_sources and bool(script.fact_checks)
    )
    required_fields = (
        script.title,
        script.hook,
        script.voiceover,
        script.shots,
        script.caption,
        script.tags,
    )
    completeness_ok = all(required_fields)
    trace_ok = bool(
        script.retrieval_trace
        and script.retrieval_trace.creative_chunks_used
        and script.retrieval_trace.operation_chunks_used
    )
    parameter_ok = verification.passed
    checks = {
        "parameter_following": parameter_ok,
        "required_fields": completeness_ok,
        "retrieval_trace": trace_ok,
        "fact_boundary": evidence_ok,
    }
    weights = {
        "parameter_following": 0.4,
        "required_fields": 0.2,
        "retrieval_trace": 0.15,
        "fact_boundary": 0.25,
    }
    score = round(sum(weights[key] for key, passed in checks.items() if passed), 3)
    return {
        "id": case["id"],
        "score": score,
        "checks": checks,
        "verification": asdict(verification),
        "retrieved_fact_names": retrieved_names,
        "expected_fact_name": expected_fact,
    }


def run_evaluation(dataset_path: Path) -> dict[str, Any]:
    dataset = load_dataset(dataset_path)
    results = [evaluate_case(case) for case in dataset["cases"]]
    threshold = float(dataset["minimum_case_score"])
    passed = [result for result in results if result["score"] >= threshold]
    pass_rate = len(passed) / len(results)
    return {
        "dataset_version": dataset["dataset_version"],
        "evaluated_at": datetime.now(UTC).isoformat(),
        "mode": "deterministic-local",
        "thresholds": {
            "minimum_case_score": threshold,
            "minimum_pass_rate": dataset["minimum_pass_rate"],
        },
        "summary": {
            "cases": len(results),
            "passed": len(passed),
            "pass_rate": round(pass_rate, 3),
            "gate_passed": pass_rate >= float(dataset["minimum_pass_rate"]),
        },
        "results": results,
    }
