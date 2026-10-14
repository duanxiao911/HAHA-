# FUNCTION ACCEPTANCE REPORT — Account Session Gate G2

## Metadata and decision

- Project / upgrade: HAHA / Account Session Gate G2
- Upgrade status: COMPLETE
- Functional acceptance: PASS for the defined internal-test G2 scope
- Production Readiness Gate: PARTIAL; not Production Candidate
- Timestamp: 2026-10-14T12:57:51+08:00
- Git: `5a5fa4f06437ea2a02645faeb399b331303c2b9c` on dirty `main`; commit alone does not identify the tested state
- Environment: local Docker JWT mode (`auth_mode=jwt`, `environment=development`, `allow_dev=false`), PostgreSQL 17, real Next.js production image, Chrome headless

## Requirement traceability

| ID | Function / states | Code | Executed evidence | Result |
|---|---|---|---|---|
| G2-01 | Internal account login → user center | `service.py:71`, `main.py:623`, `LoginForm.tsx:16` | Real API + Chrome redirect to “今天从这里继续” | PASS |
| G2-02 | Generic 401, five-attempt temporary lock | `service.py:71`, `main.py:627` | `test_repeated_bad_password_temporarily_locks_account`; browser generic error | PASS |
| G2-03 | Signed short-lived JWT with iss/aud/sub/workspace/exp/jti | `auth.py:72` | `test_login_issues_verifiable_short_lived_access_token` | PASS |
| G2-04 | Single-use refresh and replay rejection | `service.py:101`, PostgreSQL adapter `:436` | unit concurrency; real concurrent API statuses `[200,401]` | PASS |
| G2-05 | Logout revokes; repeat logout safe | `service.py:117`, `main.py:643` | API 204 then refresh 401; Chrome server revoke assertion | PASS |
| G2-06 | Role comes from DB membership | `main.py:648`, existing `resolve_membership` | API `/me` returned stored owner/viewer; API unit role test | PASS |
| G2-07 | Loading/error/password visibility/responsive login UI | `LoginForm.tsx:16`, `identity-center.css` | frontend build; Chrome 390/768/1440, no overflow | PASS |
| G2-08 | PostgreSQL + JWT Docker + real browser closure | compose/migration/E2E paths | healthy containers, migration `0008`, final E2E report | PASS |

## User and recovery flows

- Valid: login → user center → corrupt/expired access token → one automatic refresh → page recovers → logout → browser state cleared and server refresh rejected.
- Anonymous: public content stays usable with local interactions; protected user center shows an explicit login action instead of an API error.
- Negative: wrong password uses the same text as a missing account; old/replayed/revoked refresh values return 401.
- Permission: valid identity without matching membership is denied; switching business context does not enlarge server authorization.
- UI states: idle, validating, error, authenticated, logout busy, protected-empty, responsive and hydration-safe states were exercised.

## Executed checks

| Command / action | Exit | Summary |
|---|---:|---|
| `.venv\\Scripts\\python.exe -m ruff check src tests scripts` | 0 | All checks passed |
| `.venv\\Scripts\\python.exe -m pytest tests/test_auth_sessions.py -q` | 0 | 6 passed |
| `.venv\\Scripts\\python.exe -m pytest -q --basetemp <isolated>` | 0 | 82 passed, 9 skipped, 1 deprecation warning |
| `pnpm lint` | 0 | ESLint passed |
| `pnpm build` | 0 | TypeScript and 52-route production build passed |
| JWT-mode `docker compose up -d --build` | 0 | API/Worker/PostgreSQL/Redis healthy; Web running; migrate exited 0 |
| PostgreSQL migration query | 0 | `alembic_version=20261014_0008` |
| Real API login/me/refresh/logout | 0 | login true; owner; old refresh 401; logout 204; revoked refresh 401 |
| Two simultaneous real refresh calls | 0 | statuses `[200,401]`; exactly one success |
| `scripts/e2e_account_session_g2.py` | 0 | all 10 assertions true; browser errors 0 |

The nine local skips are the existing `tests/test_postgres_integration.py` group because `HAHA_TEST_POSTGRES_URL` was not exported to the host pytest process. PostgreSQL behavior was separately exercised through the real container/API; the repository integration group is configured to run in GitHub CI but the current uncommitted state has not produced a CI run.

## Sanitized artifacts

- `artifacts/e2e/account-session-g2/report.json`
- `artifacts/e2e/account-session-g2/login-390.png`
- `artifacts/e2e/account-session-g2/login-768.png`
- `artifacts/e2e/account-session-g2/login-1440.png`
- `artifacts/e2e/account-session-g2/authenticated-user-center.png`
- `artifacts/e2e/account-session-g2/invalid-login.png`

Artifacts contain no password or token values. Local database evidence at acceptance time: one internal test credential, seven historical test sessions, 27 auth audit events.

## AI eval

N/A. No AI behavior, prompt, model, retrieval, verifier or paid provider call changed in G2.

## Production Readiness Gate

| Gate | Result | Reason |
|---|---|---|
| Internal authentication correctness | PASS | Unit/API/PostgreSQL/browser evidence |
| Fail-closed configuration | PASS | Existing production/staging regression tests included in 82-pass suite |
| Migration/data integrity | PASS for forward local migration | Real `0007 → 0008`; rollback restore not exercised |
| Public browser token protection | BLOCKED | HttpOnly same-origin cookie/BFF not implemented |
| Account recovery/verification | BLOCKED | Deliberately outside internal G2 scope |
| Load/capacity/abuse controls | UNKNOWN | No load test or distributed IP rate limiter |
| Backup/restore and DR | UNKNOWN | Not exercised |
| Current GitHub CI | UNKNOWN | Worktree not committed/pushed |

Decision: G2 internal-test acceptance is PASS. Public launch and Production Candidate remain explicitly unapproved.
