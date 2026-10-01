from pathlib import Path

from haha_eval.runner import run_evaluation


def test_golden_dataset_quality_gate_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    report = run_evaluation(root / "evals" / "golden_dataset.json")

    assert report["summary"] == {
        "cases": 10,
        "passed": 10,
        "pass_rate": 1.0,
        "gate_passed": True,
    }
    unknown = next(
        item for item in report["results"] if item["id"] == "unknown-project-fail-closed"
    )
    assert unknown["retrieved_fact_names"] == []
    assert unknown["checks"]["fact_boundary"] is True
