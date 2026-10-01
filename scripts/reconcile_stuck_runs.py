"""Reconcile expired run leases with bounded retry and failed-job storage."""

from __future__ import annotations

import argparse
import json

from haha_core.bootstrap import build_repository, enqueue_run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    repository = build_repository()
    requeued, failed = repository.reconcile_expired_runs(
        max_attempts=args.max_attempts, limit=args.limit
    )
    enqueued = [run_id for run_id in requeued if enqueue_run(run_id)]
    print(
        json.dumps(
            {"requeued": requeued, "enqueued": enqueued, "failed": failed},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
