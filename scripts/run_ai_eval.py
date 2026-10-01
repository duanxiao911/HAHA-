"""Run the versioned offline AI evaluation gate and persist its report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from haha_eval.runner import run_evaluation

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT / "evals" / "golden_dataset.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "evals" / "phase-b-ai-eval.json")
    args = parser.parse_args()
    report = run_evaluation(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    if not report["summary"]["gate_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
