# Phase A Evidence 03 — Redis and Dramatiq Worker

Date: 2026-10-01
Status: PASS

## Runtime

- Redis: 8 Alpine in Docker Desktop, AOF enabled.
- Host test endpoint: `127.0.0.1:56379`.
- Dramatiq: 2.2.1, one independent worker process with two threads.
- System of record: PostgreSQL 17 integration database.

## Tests Executed

1. Redis health returned `PONG`.
2. Created a real Project, BriefVersion, and PENDING Run in PostgreSQL.
3. Published the same Run to Redis/Dramatiq twice.
4. Independent Worker claimed and completed the Run.
5. Verified exactly one ScriptVersion exists for the duplicated delivery.
6. Restarted the Redis container.
7. Published a second duplicated Run after restart and verified successful consumption.
8. Gracefully terminated the Worker after verification.

## Result Evidence

```text
run status: PASSED
claimed_by: xiaoduan:<worker-pid>
script_count: 1
platform: B站
spec: 90秒 · 16:9
```

Both the initial execution and the post-Redis-restart execution passed.

## Scope Boundary

This proves real enqueue, broker persistence/restart, worker consumption, database claim, duplicate delivery protection, and result persistence. DLQ and Stuck Run reconciliation remain intentionally unstarted until Backup/Restore passes.
