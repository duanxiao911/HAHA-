# Browser Session G3 未解决问题与风险

## 状态边界

当前适用于本机内部测试、独立开发和受控演示。不是公网生产验收，也不是 Production Candidate。

## 剩余风险

| 等级 | 状态 | 风险 | 后续动作 |
|---|---|---|---|
| 高 | UNKNOWN | 真实域名、TLS 终止、反向代理可信头与 Secure Cookie 尚未做外部环境浏览器验收 | 独立 Production Readiness Gate 使用真实 HTTPS 域名执行 Cookie/Origin/CSRF/E2E |
| 中 | UNKNOWN | GitHub CI 新 G3 job 尚未推送运行 | 用户授权提交/推送后检查真实 Actions 结果 |
| 中 | OPEN | Refresh 单飞只在单个 Next.js 进程内生效；多副本同时刷新可能产生可用性竞态 | 多副本前增加共享协调或 refresh grace/reuse family 设计并做并发压测 |
| 中 | OPEN | 会话记录没有设备名称、User-Agent、IP 风险信号和 refresh reuse detection | 下一账户安全阶段增加最小化设备元数据、异常登录与令牌家族检测 |
| 中 | INTENTIONAL | 没有 MFA、找回密码、邮箱验证、外部 IdP、公众注册 | 保持内部账户范围；公网身份方案单独立项 |
| 中 | UNKNOWN | 未执行峰值并发、长连接耗尽、BFF 大规模性能测试 | Production Gate 加入负载、SSE、刷新风暴和资源预算测试 |
| 低 | OPEN | BFF 请求体暂限 1 MiB，不适用于未来大媒体直传 | 媒体上传采用对象存储预签名，不放宽通用 BFF 代理 |
| 低 | OPEN | 配置校验在启动器与 instrumentation 中有少量重复 | 后续抽取纯函数共享模块并保留启动前强制退出语义 |
| 低 | SUPERSEDED | 历史 `scripts/e2e_account_session_g2.py` 描述 sessionStorage，不能用于当前 G3 | 仅保留为 G2 历史证据；CI 已由 G3 E2E 取代 |

## 操作注意事项

- 本机 JWT secret 是本次进程生成的临时值；重新 `docker compose up` 前必须显式提供至少 32 字符的 `HAHA_JWT_SECRET`。
- 最终 G3 验收账户密码按安全约束仅存在于测试进程，用户若要手工登录需自行设置新的内部密码，再运行 `scripts/bootstrap_internal_account.py` 轮换。
- G3 之前签发且没有 `sid` 的 access token 将返回 401，需重新登录；这是预期兼容性断点。
- `compose.staging.yaml` 设置 Secure Cookie，只应放在 TLS 终止层之后使用；直接 HTTP 不是受支持的 staging 登录方式。

## 非阻断说明

Python 回归出现的两个 `拒绝访问` 警告来自历史 `.pytest-*` 临时目录 ACL；在沙箱外指定可写 basetemp 后完整测试为 84 passed、9 skipped。该警告未影响产品运行，但历史临时目录可由用户后续自行清理。
