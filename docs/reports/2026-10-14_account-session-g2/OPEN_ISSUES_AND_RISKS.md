# OPEN ISSUES AND RISKS — Account Session Gate G2

## Metadata

- Status: COMPLETE report for a COMPLETE internal-scope upgrade
- Timestamp: 2026-10-14T12:57:51+08:00
- Git: `5a5fa4f06437ea2a02645faeb399b331303c2b9c` on dirty `main`
- Production conclusion: not Production Candidate

## Risk register

### G2-R01 — Browser tokens are script-readable

- Type / severity / status: security/privacy / HIGH for public use, MEDIUM for controlled local use / OPEN
- Evidence: `web/lib/api.ts` stores access and refresh values in `sessionStorage`.
- Impact: an XSS defect could steal the active tab's session. Likelihood is UNKNOWN; no dedicated XSS assessment was run.
- Affected: browser auth client and deployment origin.
- Mitigation: same-origin BFF using HttpOnly, Secure, SameSite cookies; CSP and dependency review.
- Owner / target: security + web owner (UNKNOWN assignment) / required before any public release.

### G2-R02 — Logout does not invalidate the current access token

- Type / severity / status: security / MEDIUM / OPEN
- Evidence: logout revokes refresh state; JWT remains valid until its 15-minute `exp`.
- Impact: a copied access token can be used during its remaining lifetime.
- Mitigation: keep short TTL; add token/session version or denylist for high-risk operations.
- Owner / target: API owner UNKNOWN / before sensitive commerce or reviewer actions.

### G2-R03 — No public recovery, verification or MFA

- Type / severity / status: correctness/security/operations / MEDIUM / ACCEPTED FOR INTERNAL G2
- Evidence: architecture explicitly rejects registration, email recovery, SMS/OAuth and MFA in this stage.
- Impact: administrators must rotate internal credentials; public users cannot safely self-recover.
- Likelihood: certain if opened publicly.
- Mitigation: select an identity provider and define email/phone verification, recovery, MFA and support SOP.
- Owner / target: product/security UNKNOWN / before public account onboarding.

### G2-R04 — Abuse protection is account-only

- Type / severity / status: security/capacity / MEDIUM / OPEN
- Evidence: five failed attempts lock a database credential, but there is no IP/device/distributed rate limiter.
- Impact: password spraying and denial-by-lockout remain possible on a public endpoint.
- Mitigation: Redis-backed rate limiting, progressive delay, alerting, proxy/WAF limits.
- Owner / target: platform/security UNKNOWN / before internet exposure.

### G2-R05 — Session-family incident response is incomplete

- Type / severity / status: security/recovery / MEDIUM / OPEN
- Evidence: atomic rotation rejects replay, but replay does not revoke all descendant sessions and no revoke-all API exists.
- Impact: theft detected after the legitimate refresh may not terminate the attacker's replacement token.
- Mitigation: session-family identifier, reuse detection, family revocation, user/admin session inventory.
- Owner / target: API/security UNKNOWN / before public launch.

### G2-R06 — Secret rotation and key management are not implemented

- Type / severity / status: deployment/maintenance/security / MEDIUM / OPEN
- Evidence: one symmetric `HAHA_JWT_SECRET`; no key ID or dual-key rotation window.
- Impact: secret rotation logs out users or requires coordinated downtime; host environment remains the trust boundary.
- Mitigation: secret manager, `kid`, overlapping verification keys, documented rotation drill.
- Owner / target: platform UNKNOWN / before multi-host staging.

### G2-R07 — CI evidence is pending

- Type / severity / status: deployment/regression / MEDIUM / UNKNOWN
- Evidence: CI now contains backend PostgreSQL and account-session Chrome jobs, but worktree is uncommitted/unpushed.
- Impact: Linux runner differences have not yet been confirmed for this exact state.
- Mitigation: commit/push only on user instruction, then require green branch protection checks.
- Owner / target: repository owner / next commit cycle.

### G2-R08 — Capacity, backup and restore evidence is absent

- Type / severity / status: performance/recovery/data integrity / MEDIUM / UNKNOWN
- Evidence: functional Docker tests only; no auth load, retention, backup or restore exercise.
- Impact: peak login latency, audit growth and recovery time are unsupported conclusions.
- Mitigation: set SLOs, run PBKDF2/login load test, define session/audit retention, execute restore drill.
- Owner / target: platform/data owners UNKNOWN / Production Readiness Gate.

### G2-R09 — Local test account remains in the development database

- Type / severity / status: security/operations / LOW while loopback-only / OPEN
- Evidence: one credential exists in the local PostgreSQL volume and uses a test-only password.
- Impact: unsafe if this volume or ports are reused for a shared environment.
- Mitigation: rotate/bootstrap a private credential before demos; remove test account or recreate volumes before external hosting.
- Owner / target: local operator / before sharing host access.

## Coverage summary

- Correctness, permissions, forward migration and local data integrity: directly tested.
- Security/privacy, recovery, capacity, observability and deployment: partially covered; open items above.
- Cost: LOW current incremental cost; future audit retention cost UNKNOWN.
- Dependencies/licenses/IP: no new dependency or content asset; N/A for newly introduced license/IP risk.
