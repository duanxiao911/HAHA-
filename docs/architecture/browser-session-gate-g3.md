# G3 浏览器安全会话 Gate 架构决策

- 日期：2026-10-14
- 状态：Accepted for implementation
- 范围：内部测试、独立开发、比赛/投资展示环境
- 明确不包含：公众注册、第三方登录、生产发布、Production Candidate 判定

## 1. 业务目标与验收标准

G2 已提供真实账户、短期 JWT、旋转 Refresh Token 与退出登录，但浏览器仍将令牌保存在 `sessionStorage`。G3 的目标是把浏览器认证边界收回同源服务端，并允许用户查看和撤销自己的登录会话。

验收标准：

1. 浏览器 JavaScript、`localStorage`、`sessionStorage` 和业务 JSON 响应均不可读取 access/refresh token。
2. access/refresh token 仅由 Next.js 同源 BFF 写入 `HttpOnly` Cookie；Cookie 至少设置 `SameSite=Lax`、`Path=/`，受控 HTTPS 环境设置 `Secure`。
3. 所有有副作用的同源请求同时校验请求来源与双提交 CSRF Token；缺失或错误时返回 403，且请求不得到达 FastAPI。
4. BFF 只代理 `/api/**`，不接受任意目标 URL，不透传浏览器 Cookie、Host 或客户端 Authorization。
5. access token 过期后，BFF 使用 HttpOnly refresh cookie 单飞轮换并重放原请求一次；轮换失败时清除会话 Cookie。
6. 后端访问令牌绑定持久会话 ID；会话撤销后，即使 access token 尚未过期，后续受保护请求也必须被拒绝。
7. 用户可以列出本人当前工作空间的会话、撤销指定会话、撤销全部会话；不可查看或撤销其他账户的会话。
8. GitHub Pages 仍是无认证静态演示，不承载真实账户会话；真实认证只在有 Next.js Server Runtime 的环境验收。

## 2. 最小充分架构

```text
Browser
  ├─ HttpOnly: haha_access / haha_refresh
  ├─ readable: haha_csrf (随机值，不是身份凭据)
  └─ same-origin /api/*
             │ Origin + CSRF
             ▼
Next.js Route Handlers (BFF)
  ├─ login / session / logout
  ├─ allowlisted /api/** reverse proxy
  ├─ refresh rotation and one retry
  └─ token fields stripped from browser responses
             │ Authorization: Bearer <server-only cookie>
             ▼
FastAPI
  ├─ JWT signature / issuer / audience / expiry
  ├─ sid -> active auth_sessions record
  ├─ database membership and role
  └─ domain authorization
```

不引入新的认证框架、反向代理产品、Redis 会话层或第三方身份服务。沿用 G2 的 JWT 和数据库会话，只增加服务端浏览器适配层。

## 3. 接口契约

### Next.js 同源接口

| Method | Path | 用途 | 关键约束 |
|---|---|---|---|
| POST | `/api/session/login` | 登录并写入 Cookie | 校验同源 Origin；响应不含 token |
| GET | `/api/session` | 获取浏览器会话状态 | 可轮换 refresh；确保 CSRF Cookie 存在 |
| POST | `/api/session/logout` | 撤销当前 refresh 会话并清 Cookie | 同源 Origin + CSRF |
| ALL | `/api/backend/api/**` | 受限 FastAPI 代理 | 只允许相对 `/api/**`；变更请求校验 CSRF |

### FastAPI 接口

| Method | Path | 用途 |
|---|---|---|
| GET | `/api/auth/sessions` | 列出本人会话，标记当前会话 |
| DELETE | `/api/auth/sessions/{session_id}` | 撤销本人指定会话 |
| DELETE | `/api/auth/sessions` | 撤销本人全部会话 |

会话 DTO 不返回 refresh token/hash，仅返回 `id`、状态、创建/最近使用/过期时间和 `is_current`。

## 4. 安全决策

- Cookie 名称不使用 `__Host-` 前缀，因为本机真实验收仍使用 HTTP；生产 HTTPS 配置必须显式启用 `Secure`，预发布/生产若关闭则启动失败。
- CSRF 使用“同源 Origin + 双提交 Cookie/Header”双层校验。CSRF 值不是认证凭据，可由前端读取。
- BFF 不替代后端授权。FastAPI 继续在数据源附近验证会话、成员资格、角色和资源所有权。
- Refresh Token 仅发往固定的内部 API 地址；浏览器不能覆盖该地址。
- 静态演示不降级到浏览器持有 JWT；它保持 `NEXT_PUBLIC_DEMO_MODE=true` 的无认证示例能力。

## 5. 测试计划

1. Python 单元/集成：`sid` 声明、撤销后 access 即时失效、会话所有权、单个/全部撤销、refresh 轮换回归。
2. Next.js：TypeScript/lint/build；普通 standalone 与 GitHub Pages 静态演示分别构建。
3. 真实 Docker/PostgreSQL：JWT 模式启动，BFF 登录、Cookie 属性、CSRF 拒绝/接受、会话清单与撤销。
4. 真实 Chromium：登录、刷新后恢复、用户中心读取、`sessionStorage`/`localStorage` 无 token、`document.cookie` 不可见 access/refresh、退出后受保护请求失败。

未执行的结论标记 `UNKNOWN`；真实阻断标记 `BLOCKED`；不得以构建或 Mock 结果替代业务闭环。
