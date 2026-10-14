# ARCHITECTURE CHANGE REPORT — Account Session Gate G2

## Metadata

- Project: HAHA 非遗图文脚本创作与视频内容社区平台
- Upgrade: G2 正式账户与可撤销会话闭环（内部测试范围）
- Status: COMPLETE
- Timestamp: 2026-10-14T12:57:51+08:00
- Git: `5a5fa4f06437ea2a02645faeb399b331303c2b9c` on `main`
- Worktree: dirty；上述 commit 不完整标识本报告验收的 G1/G2 工作区状态
- Environment: Windows 11 host、Docker Desktop Linux containers、PostgreSQL 17、Redis 8、FastAPI、Next.js 16.3.6、Chrome headless；Web/API 仅绑定 `127.0.0.1`

## Before / after

| Area | Before G2 | After G2 |
|---|---|---|
| Authentication | G1 依赖显式 opt-in 的开发请求头身份；`/login` 为说明页 | 内部账户邮箱/密码登录，15 分钟 HS256 JWT，7 天不透明刷新会话 |
| Authorization | PostgreSQL membership 服务端判权 | 保持不变；JWT 不携带可信 role，实际 role 仍从 membership 读取 |
| Session lifecycle | 无真实登录、轮换、撤销 | 登录、原子单次刷新轮换、幂等退出、服务端撤销、认证审计 |
| Credentials | 无平台凭据存储 | PBKDF2-HMAC-SHA256、随机 32-byte salt、默认 600000 次；不存在账户执行等成本计算 |
| Browser | 无真实会话状态 | `sessionStorage` 标签页会话、401 自动刷新一次、退出清理、SSR-safe 外部存储订阅 |
| Data | `users/workspaces/memberships` | 新增 `auth_credentials/auth_sessions/auth_audit_events` |

## Decisions and alternatives

架构决定记录在 [`docs/architecture/account-session-gate-g2.md`](../../architecture/account-session-gate-g2.md)。采用现有单体 FastAPI + Repository + PostgreSQL 边界，没有增加身份微服务或第三方 SDK。

- Chosen: 自管内部账户 adapter，满足内部开发、比赛和投资展示的真实会话需要。
- Rejected now: 公众注册、短信、微信/OAuth、邮件找回；缺少提供商、合规和运营边界。
- Deferred before public release: 同源 BFF + HttpOnly/Secure/SameSite Cookie。当前 `sessionStorage` 只适用于受控内部阶段。

## Modified implementation paths

- Domain/service/port: `src/haha_auth/domain.py`, `src/haha_auth/service.py:42`, `src/haha_auth/repository.py:15`
- JWT and API: `src/haha_api/auth.py:44`, `src/haha_api/auth.py:72`, `src/haha_api/main.py:623`
- SQLite/PostgreSQL adapters: `src/haha_core/repository.py:406`, `src/haha_core/sqlalchemy_repository.py:436`
- Migration: `migrations/versions/20261014_0008_account_sessions_g2.py:14`
- Internal bootstrap: `scripts/bootstrap_internal_account.py`
- Browser client/UI: `web/lib/api.ts:14`, `web/app/login/LoginForm.tsx:16`, `web/app/identity/IdentityCenter.tsx:26`, `web/components/community/AppHeader.tsx:46`
- Regression/CI: `tests/test_auth_sessions.py`, `tests/test_postgres_integration.py:124`, `.github/workflows/ci.yml:200`, `scripts/e2e_account_session_g2.py`

## API, state and permissions

- `POST /api/auth/login`: generic invalid-credential error; five failures lock the credential for 15 minutes.
- `POST /api/auth/refresh`: verifies stored SHA-256 digest and performs conditional database update; concurrent replay yields exactly one success.
- `POST /api/auth/logout`: idempotently revokes a matching refresh session.
- `GET /api/auth/me`: requires Bearer token and resolves role from membership.
- JWT claims: `sub`, `workspace_id`, `iss`, `aud`, `iat`, `exp`, `jti`; client-supplied role is not trusted.
- Browser state: access/refresh values are kept only in the current tab and are never included in evidence output.

AI workflow: N/A. G2 does not change model routing, context, verifier, eval data, prompts, or paid calls.

## Migration, rollout, rollback and recovery

- Additive migration `20261014_0008`; real PostgreSQL migrated from `0007` to `0008` with exit 0.
- Rollout order: apply migration → set JWT issuer/audience/secret → start API/Web → bootstrap controlled accounts via environment-only password → run smoke/E2E.
- Application rollback: restore prior images while retaining additive tables. Schema downgrade deletes credentials, sessions and auth audit; it is destructive and must not run without an explicit backup/discard decision.
- Compromised refresh session: logout/revoke the row; current implementation does not yet expose an administrator revoke-all endpoint.

## Non-functional impact

- Security/privacy: improves fail-closed identity and auditability; browser storage and access-token revocation delay remain documented risks.
- Performance: login pays configurable PBKDF2 cost; refresh is one indexed read plus atomic update. Load/capacity is UNKNOWN.
- Reliability: refresh replay protection is database-atomic across API instances. Backup/restore exercise is UNKNOWN.
- Observability: login/refresh success metrics and structured auth audit events exist; credential bodies/tokens are not logged.
- Cost: no new paid service or dependency; PostgreSQL storage growth is bounded by session/audit retention policy, which is not yet automated.
- Maintenance/licensing/IP: no new runtime library; N/A for new third-party licensing or proprietary AI assets.

## Evidence and unresolved questions

- PASS: 82 Python tests, ruff, frontend lint/build, PostgreSQL migration, real API session flow, concurrent PostgreSQL refresh, Chrome E2E.
- UNKNOWN: uncommitted GitHub Actions result, public traffic capacity, disaster recovery, external identity-provider compliance.
- This report does not declare Production Candidate or Production Ready.
