# P0 security remediation evidence — 2026-10-09

## Repository state before remediation

- Branch: `main...origin/main [ahead 1]`
- Local HEAD: `5f9975b docs: add phase abc upgrade report`
- Remote-tracking HEAD: `828f066 feat: complete phase c5 release package`
- Pre-existing untracked path preserved: `.test-artifacts/`
- GitHub Actions baseline queried on 2026-10-10: run `37937267478`, workflow `HAHA CI`, commit
  `828f066`, completed `success` in 3m17s. The local P0 changes are not pushed, so no remote CI claim is
  made for them.

## Automated verification

### Security-targeted regression

```text
.venv\Scripts\python.exe -m pytest \
  tests/test_api.py tests/test_asset_context.py tests/test_model_router.py \
  tests/test_creator_service.py -q -k "<P0 security cases>"

10 passed, 44 deselected, 1 warning
```

The exact P0 selection covers locked defaults, dev opt-in, staging/production rejection, JWT workspace
spoofing, DTD/entity rejection, ZIP ratio/entry/aggregate budgets, JSON prompt isolation and critical-fact
grounding.

The broader changed-component run was:

```text
.venv\Scripts\python.exe -m pytest \
  tests/test_asset_context.py tests/test_api.py tests/test_model_router.py \
  tests/test_creator_service.py -q -k "not sqlite_repository_migrates_legacy_run_schema"

53 passed, 1 deselected, 1 warning
```

The deselected test is an unrelated legacy SQLite migration test that requests pytest `tmp_path`.
The host currently denies access to pytest-created Windows temporary directories.

### Backend suite

```text
.venv\Scripts\python.exe -m pytest tests -q \
  -k "not sqlite_repository_migrates_legacy_run_schema"

77 passed, 6 skipped, 1 deselected, 1 warning
exit code: 0
```

The warning is the pre-existing Starlette `httpx` deprecation warning. The skipped tests are existing
environment-dependent integration cases.

### Static and frontend checks

```text
.venv\Scripts\ruff.exe check src tests
All checks passed!

pnpm lint
exit code: 0

pnpm build
Compiled successfully
Finished TypeScript
Generated static pages (6/6)
exit code: 0
```

The first sandboxed frontend build reached successful compilation and then hit `spawn EPERM`; the same
build was rerun with child-process permission and completed successfully.

### Compose configuration

```text
docker compose config --quiet
exit code: 0

POSTGRES_PASSWORD=<test> HAHA_JWT_SECRET=<32+ char test secret> \
docker compose -f compose.staging.yaml config --quiet
exit code: 0
```

## Regression coverage map

| Threat | Test evidence |
|---|---|
| Missing auth configuration | `tests/test_api.py:309` |
| Dev auth without explicit opt-in | `tests/test_api.py:322` |
| Staging/production dev-auth attempt | `tests/test_api.py:332` |
| Missing/invalid JWT and spoofed workspace header | `tests/test_api.py:260-284` |
| XML entity expansion | `tests/test_asset_context.py:36` |
| ZIP high compression ratio | `tests/test_asset_context.py:52` |
| Oversized document entry | `tests/test_asset_context.py:59` |
| Aggregate uncompressed budget | `tests/test_asset_context.py:73` |
| Pseudo-XML prompt injection | `tests/test_model_router.py:147` |
| Ungrounded critical fact | `tests/test_creator_service.py:282` |

## Evidence limitations

- No live provider call was made in this remediation run; online adversarial model evaluation belongs to
  the independent Production Readiness Gate.
- No Production Candidate status is asserted.
