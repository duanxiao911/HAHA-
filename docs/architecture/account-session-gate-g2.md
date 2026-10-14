# Account Session Gate G2

## Goal

为内部测试、独立开发、比赛和投资展示提供真实的账户登录与可撤销会话，不开放公众注册，不伪装成已经接入手机、微信或第三方 OAuth。

## Scanner / reuse decision

- KEEP：`auth.py` 的 fail-closed 环境校验、HS256 验签、issuer/audience/expiry 校验。
- KEEP：`users`、`workspaces`、`memberships` 及服务端资源归属校验。
- ADAPT：`/login` 从静态说明页改为真实登录表单。
- ADD：凭据、刷新会话与认证审计表；内部账户引导脚本；登录/刷新/退出/当前会话 API。
- REJECT：开放注册、短信验证码、OAuth、社交登录、第三方身份 SDK；当前没有相应提供商、预算和合规依据。

## ADR

G2 使用平台自管内部账户作为可替换的 authentication adapter：PBKDF2-HMAC-SHA256（每账户随机盐、600000 次）、15 分钟访问 JWT、7 天不透明刷新令牌、服务端仅存刷新令牌 SHA-256 摘要、每次刷新轮换、退出撤销。连续失败 5 次锁定 15 分钟，并使用统一错误信息降低账户枚举风险。

授权仍由数据库 membership 决定；JWT 只证明 `sub + workspace_id`，客户端提供的 role 不作为权限依据。

## API

- `POST /api/auth/login`：email、password、workspace_id -> access_token、refresh_token、expires_in、account。
- `POST /api/auth/refresh`：轮换 refresh token。
- `POST /api/auth/logout`：撤销 refresh session，幂等。
- `GET /api/auth/me`：返回当前服务端成员身份和账户摘要。

登录与刷新端点采用通用失败文案；令牌不写日志；浏览器访问令牌与刷新令牌暂存在 sessionStorage，关闭标签页即消失。正式公网发布前应迁移到同源 BFF + HttpOnly/Secure/SameSite cookie。

## Acceptance

- G2-01：有效内部账户可以登录并打开用户中心。
- G2-02：错误密码统一返回 401；连续 5 次后锁定。
- G2-03：访问令牌包含正确 iss/aud/sub/workspace/exp/jti 且可被现有鉴权验证。
- G2-04：刷新令牌单次使用；轮换后旧令牌失效。
- G2-05：退出后刷新失败；退出重复调用幂等。
- G2-06：JWT role 伪造不能越过数据库 membership。
- G2-07：登录页具备 loading/error/success、密码显隐、键盘标签和移动端布局。
- G2-08：真实 PostgreSQL、JWT 模式 Docker、Chrome 登录—刷新—退出闭环通过。

