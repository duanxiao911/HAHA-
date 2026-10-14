# Browser Session G3 功能验收报告

## 结论

G3 在本机真实 Docker/PostgreSQL/Redis/FastAPI/Next.js/Chrome 环境内完成验收，内部测试范围为 **PASS**。公网 TLS、真实域名、多副本和外部身份提供商未验收，均不在本次 PASS 范围内。本报告不宣布 Production Candidate。

## 自动化测试

| 层级 | 命令/环境 | 结果 |
|---|---|---|
| Python 全量 | `.venv/Scripts/python.exe -m pytest -q --basetemp .pytest_tmp/g3-final` | **84 passed, 9 skipped** |
| Python 质量 | `.venv/Scripts/python.exe -m ruff check .` | **PASS**；仅报告两个历史 pytest 目录 ACL 警告 |
| 前端 lint | `pnpm lint` | **PASS** |
| TypeScript | `node_modules/.bin/tsc --noEmit` | **PASS** |
| 社区契约 | `pnpm test:community` | **5 passed** |
| Standalone | `pnpm build` 及 Docker Web build | **PASS**；55 routes，4 个动态 BFF routes |
| 静态演示 | `pnpm build:demo` | **PASS**；52 个静态/SSG routes，不包含 BFF |
| YAML | CI、Pages、三份 Compose `yaml.safe_load` | **PASS** |

9 个 skip 是既有的外部集成条件标记；真实 PostgreSQL/Redis/Docker 链路已由下面的独立验收覆盖，未将 skip 计作 PASS。

## 后端会话回归

`tests/test_auth_sessions.py` 与 `tests/test_api.py` 实际验证：

- JWT 包含并强制验证 `sid`。
- Refresh Token 原子轮换，旧 token 重放被拒绝。
- logout 后，对应 access token 即时返回 401。
- 用户只能列出和撤销自己的会话，跨账户撤销返回 404。
- 撤销单个会话不影响同账户其他有效会话。
- 撤销全部会话后当前 access token 立即返回 401。

## 真实浏览器验收

- 脚本：`scripts/e2e_browser_session_g3.py`
- 证据：`artifacts/e2e/browser-session-g3/report.json`
- 截图：`artifacts/e2e/browser-session-g3/authenticated-session-settings.png`
- 最终结果：**18/18 assertions PASS，0 browser errors**

通过项：

1. 未登录用户中心引导登录。
2. 真实内部账户登录成功。
3. Web Storage 中不存在 access/refresh token。
4. JavaScript 只能读取 CSRF Cookie，不能读取 access/refresh Cookie。
5. access 与 refresh Cookie 均为 HttpOnly、SameSite=Lax。
6. 缺失 CSRF 的变更请求返回 403。
7. BFF 不允许代理原始 refresh token 端点。
8. access cookie 被替换为无效值后，BFF 自动刷新并恢复。
9. refresh token 在服务端轮换。
10. 用户中心显示当前会话。
11. “退出全部设备”撤销服务端会话并清除浏览器凭据。
12. 登录响应 JSON 不含 access/refresh token。
13. 最终 logout 返回 204。

## 容器与运行态

最终探测：

```json
{"api_status":"ready","database":"ok","redis":"ok","web_status":200,"session_status":200,"session_body":"{\"authenticated\":false}","csrf_cookie":true}
```

运行服务：API/PostgreSQL/Redis/Worker 均 healthy；Web 使用 `node start-server.mjs`，`127.0.0.1:3000` 返回 200。

## Fail-closed 实测

一次性运行 Web 镜像并设置 `HAHA_ENVIRONMENT=staging`、`HAHA_COOKIE_SECURE=false`：启动器打印“staging/production 必须设置 HAHA_COOKIE_SECURE=true”，容器状态 `exited`，退出码 `1`。因此预发布/生产漏配 Secure Cookie 不会进入可服务状态。

## CI 回归

`.github/workflows/ci.yml:200` 新增独立 `browser-session-e2e` job，使用 JWT Docker 全栈、临时内部账户和 Chrome 执行同一 G3 脚本并上传证据。当前工作区尚未推送，所以 GitHub 远端执行结果为 **UNKNOWN**，不能写成 PASS。
