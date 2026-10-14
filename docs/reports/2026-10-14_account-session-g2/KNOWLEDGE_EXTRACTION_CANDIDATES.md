# KNOWLEDGE EXTRACTION CANDIDATES — Account Session Gate G2

## Metadata and authority

- Status: COMPLETE candidate queue
- Timestamp: 2026-10-14T12:57:51+08:00
- Git: `5a5fa4f06437ea2a02645faeb399b331303c2b9c` on dirty `main`
- Authority: review queue only; no global knowledge tree was modified.

## Candidate 1 — JWT authenticates identity; database membership authorizes it

- Category: security architecture
- Context/evidence: G2 token contains user/workspace identity only; `/api/auth/me` returned the role stored in PostgreSQL. Existing authorization tests remained green.
- Principle: client claims should not be the source of mutable workspace permission.
- Reusable pattern: signed identity token → server-side membership lookup → scoped principal.
- Boundary/tradeoff: adds a database read; high-scale systems may use short authorization caches with explicit invalidation.
- Confidence: HIGH.
- Sanitization: contains no secret or private account data.
- Proposed destination: authentication/authorization engineering patterns (UNKNOWN approval).
- Next validation: multi-instance cache/revocation test if caching is introduced.

## Candidate 2 — Refresh rotation must be atomic in the persistence adapter

- Category: concurrency/security
- Context/evidence: a read-then-save design allowed a theoretical concurrent replay. Conditional update on `id + expected_hash + revoked_at=''` produced real PostgreSQL concurrent statuses `[200,401]`.
- Principle: “single use” is a database state transition, not an application-layer convention.
- Reusable pattern: compare-and-swap digest rotation and require `rowcount == 1`.
- Boundary/tradeoff: protects one session row; session-family replay response still needs separate design.
- Confidence: HIGH.
- Sanitization: no token values recorded.
- Proposed destination: session-management/concurrency patterns (UNKNOWN approval).
- Next validation: repeat under multi-process load and fault injection.

## Candidate 3 — Browser storage is an SSR external store

- Category: frontend/Next.js reliability
- Context/evidence: directly reading `sessionStorage` during render caused React production hydration error #418. `useSyncExternalStore` with a stable server snapshot removed the exception; final Chrome count was zero.
- Principle: server-rendered markup and the first client snapshot must agree.
- Reusable pattern: subscribe/getSnapshot/getServerSnapshot adapter around browser-only state.
- Boundary/tradeoff: corrects hydration and cross-component updates; it does not make script-readable tokens safe for public use.
- Confidence: HIGH.
- Sanitization: no private data.
- Proposed destination: SSR/browser-state engineering patterns (UNKNOWN approval).
- Next validation: add an automated hydration regression assertion to every SSR session surface.

## Candidate 4 — Public content and private personalization need separate failure boundaries

- Category: product/API integration
- Context/evidence: content detail now keeps local viewing/interaction available when anonymous and only attempts server asset/history sync with a valid session; user center explicitly asks for login.
- Principle: optional personalization failure should not break public consumption.
- Reusable pattern: public core action + authenticated enrichment, each with truthful copy and independent errors.
- Boundary/tradeoff: not suitable when the primary resource itself is private.
- Confidence: HIGH.
- Sanitization: no user data.
- Proposed destination: progressive-auth product patterns (UNKNOWN approval).
- Next validation: anonymous and expired-session E2E on every public page that writes personalization.

## Next-iteration recommendations

1. G3 should start with same-origin HttpOnly cookie/BFF and CSRF design, not public registration UI.
2. Add session inventory, revoke-all and session-family replay response before reviewer, seller or commerce privileges become real.
3. Add Redis/proxy abuse controls and auth SLO/load evidence.
4. After user-authorized commit/push, require the new PostgreSQL and JWT Chrome CI jobs to pass before changing readiness status.
5. Run an independent Production Readiness Gate; do not infer it from G2 functional PASS.
