# Browser Session G3 架构变更报告

## 交付元数据

- 时间：2026-10-14T15:18:53+08:00
- 基线 Git Commit：`5a5fa4f06437ea2a02645faeb399b331303c2b9c`
- 工作区状态：G1/G2/G3 变更尚未提交；本报告不能替代 Git commit 或远端 CI
- Web 镜像：`sha256:4a7d0c163b4e3201ccd75b961d87dc31ade3bbb1a8a570843373fa01714b707f`
- API 镜像：`sha256:44600ba056c3eed58f489da3419b978a31023f59e0a42d01160594e8198321dc`
- 环境：Windows 主机、Docker Desktop、PostgreSQL 17、Redis 8、FastAPI、Next.js 16.3.6、真实 Chrome
- 发布结论：未执行公网发布，未宣布 Production Candidate

## 变更前

G2 在浏览器 `sessionStorage` 保存 access/refresh token，浏览器直接调用 FastAPI。退出可以撤销 refresh token，但已签发的短期 access token 在自然过期前仍可使用；用户也无法查看或撤销其他登录会话。

## 变更后

```text
Browser
  ├─ HttpOnly haha_access / haha_refresh
  ├─ readable haha_csrf（非身份凭据）
  └─ same-origin request
       ↓ Origin + CSRF
Next.js BFF
  ├─ login/session/logout Route Handlers
  ├─ allowlisted /api/** proxy
  ├─ server-only refresh rotation
  └─ strip token fields
       ↓ server-side Authorization
FastAPI
  ├─ JWT signature/issuer/audience/expiry
  ├─ sid -> active auth_sessions
  ├─ membership/role/resource authorization
  └─ session list/revoke/audit
```

## 主要代码路径

- [`docs/architecture/browser-session-gate-g3.md`](../../architecture/browser-session-gate-g3.md)：目标、接口和验收契约。
- `src/haha_api/auth.py:30,73`：Principal 增加 `session_id`，JWT 强制带 `sid`。
- `src/haha_auth/service.py:128-176`：会话有效性、清单、单个/全部撤销。
- `src/haha_api/main.py:183,664-696`：每次受保护请求校验数据库会话及会话管理 API。
- `web/lib/bff-session.ts:6-148`：HttpOnly Cookie、Origin/CSRF、固定内部 API、刷新单飞与响应过滤。
- `web/app/api/session/**`：登录、会话恢复和退出。
- `web/app/api/backend/[...path]/route.ts:10-59`：受限反向代理，并阻断 login/refresh/logout 原始令牌端点。
- `web/lib/api.ts:70-156`：浏览器认证状态改为 BFF 会话，不再保存令牌。
- `web/app/identity/IdentityCenter.tsx:94`：登录设备清单、单个撤销和退出全部设备。
- `web/scripts/start-server.mjs:1-23`：预发布/生产 Cookie 安全配置在加载 Next server 前 fail-closed。

## 关键架构决策

1. 复用 G2 JWT 与 `auth_sessions`，不增加新认证框架或 Redis 会话层。
2. BFF 只承担浏览器凭据适配；FastAPI 仍在数据源附近完成授权。
3. access token 绑定持久会话 ID，撤销后立即拒绝，不等待 JWT 过期。
4. GitHub Pages 无 Server Runtime，因此静态演示构建通过 `build:demo` 明确隔离 `app/api`；不把认证端点错误地强制静态化。
5. Next instrumentation 的异常未必终止容器，因此 Docker 改用前置启动器做确定性退出，instrumentation 仅作为第二道校验。

## 数据与兼容性

- 无新增数据库迁移；复用 G2 的 `auth_sessions` 表。
- G3 之前不含 `sid` 的 access token 会被拒绝，这是预期的安全失效行为；用户需要重新登录。
- Refresh Token 哈希仍只保存在数据库，明文只存在于 HttpOnly Cookie 和服务端转发内存。
- GitHub Pages 继续保留产品静态演示能力，但不具备也不伪装真实账户功能。

## 回滚边界

代码可回滚到 G2，但这会重新引入浏览器可读令牌和撤销延迟，不建议作为正常回滚目标。数据库没有 G3 schema 变更；必要时回滚 Web/API 镜像即可。回滚前应撤销现有内部测试会话并要求重新登录。
