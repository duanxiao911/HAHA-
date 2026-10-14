# Browser Session G3 工程知识候选

以下仅为候选，不修改全局知识树。

## 候选 1：短期 JWT 也需要绑定可撤销服务端会话

- 问题：只撤销 refresh token 时，已签发 access token 会继续有效到过期。
- 做法：JWT 加 `sid`，每次受保护请求同时校验签名、声明、数据库会话状态和成员资格。
- 适用：需要“退出全部设备”“管理员踢下线”或安全事件即时止损的内部/企业应用。
- 代价：每次请求增加一次会话读取；后续可在不牺牲撤销语义的前提下评估短缓存。

## 候选 2：Next.js BFF 的 Origin 不能只看容器内 request URL

- 问题：standalone 容器中的 `request.nextUrl.origin` 可能是容器主机名，而浏览器 Origin 是外部 Host。
- 做法：在受控代理链中按 `X-Forwarded-Host/Proto`，否则按 `Host` 重建外部 origin；代理必须覆盖而非追加这些头。
- 验证：真实 Docker Chrome 首轮发现合法登录被 403，修正后 18/18 通过。

## 候选 3：instrumentation 报错不等于容器确定性启动失败

- 问题：Next.js instrumentation 抛错后，Node 进程仍可能存活，Docker 只看进程会误判已启动。
- 做法：在启动 `server.js` 前运行独立配置校验并以非零码退出；instrumentation 作为第二道检查。
- 验证：修复前容器 `RUNNING=true`；修复后 `STATUS=exited EXIT_CODE=1`。

## 候选 4：静态演示与真实认证应在构建边界显式隔离

- 问题：`output: export` 不支持动态认证 Route Handlers；把会话 GET 强制静态化会造成认证缓存风险。
- 做法：静态演示构建临时隔离 server-only routes 并自动恢复源码，真实环境使用 standalone BFF。
- 验证：standalone 55 routes（含 4 个动态 BFF routes），静态演示 52 routes且构建成功。

## 候选 5：浏览器凭据防护需要组合控制

- 组合：HttpOnly token Cookie + SameSite + 同源 Origin + 双提交 CSRF + 后端资源授权 + 原始 token 端点禁代理。
- 原因：任一单项都不能替代其他边界；隐藏前端按钮也不是授权。
- 验证：Web Storage 无 token、JS 仅见 CSRF、缺 CSRF 403、token endpoint 404、后端撤销即时 401。

## 建议复核条件

在收录知识库前，应由安全/平台角色复核：可信代理头模型、多副本 refresh 协调、TLS Cookie 行为、CSRF 策略和数据最小化要求。不得收录测试密码、JWT secret、真实用户信息或私有业务提示词。
