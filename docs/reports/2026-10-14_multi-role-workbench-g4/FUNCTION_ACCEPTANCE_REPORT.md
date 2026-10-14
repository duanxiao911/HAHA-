# G4 多身份工作台功能验收报告

## 元数据与结论

- 日期：2026-10-14 17:19 +08:00
- 实现提交：`72ad2cee28eaa4fade496a4b7d29f89a93dfb428`
- 验收环境：本机真实 Docker Compose；JWT；PostgreSQL 17；Redis 8；FastAPI；Next.js；无头 Chrome
- 范围结论：`PASS`
- 生产就绪结论：`PARTIAL`；远端 CI、外部 HTTPS、备份恢复和真实业务 API 不在本轮通过范围

## 功能验收矩阵

| 验收项 | 结果 | 证据 |
|---|---|---|
| 未登录访问受保护用户中心 | `PASS` | 浏览器 E2E `protected_entry=true` |
| JWT 登录并恢复用户中心 | `PASS` | `login=true` |
| 默认浏览者工作台 | `PASS` | `workbench_tab=true`、`viewer_boundary_visible=true` |
| 客户端伪造 `role=admin` 不越权 | `PASS` | `query_role_cannot_escalate=true` |
| 创作者开通与切换 | `PASS` | `creator_activated=true`、`creator_switched=true` |
| 创作者真实项目创建与刷新恢复 | `PASS` | `creator_project_created=true`、`creator_project_restored=true` |
| 学习者开通、切换和想学资料持久化 | `PASS` | 三项对应断言均为 `true` |
| AI 学习能力边界不伪装完成 | `PASS` | 页面明确“等待真实模型 API” |
| 买家工作台不伪造订单 | `PASS` | `commerce_is_honestly_blocked=true` |
| 浏览器运行无异常 | `PASS` | `browser_errors=0` |
| API/数据库/Redis 就绪 | `PASS` | `/health=ok`；`/ready` database/redis 均为 `ok` |

机器可读证据：`artifacts/e2e/role-workbench-g4/report.json`（本地忽略，不提交 Git）。
视觉证据：`artifacts/e2e/role-workbench-g4/multi-role-workbench.png`（1440px 真实页面长截图）。

## 已执行命令与结果

### 后端

```text
.venv\Scripts\python.exe -m pytest -q
88 passed, 11 skipped, 1 warning in 3.24s
```

11 项跳过项是需要 `HAHA_TEST_POSTGRES_URL` 的独立 PostgreSQL pytest；不能把它们记为本地单测 PASS。
同一轮真实 Docker 浏览器验收已实际使用 PostgreSQL。GitHub Actions 配置会在 PostgreSQL service 下执行这些测试，
但远端结果在本报告生成时为 `UNKNOWN`（尚未推送触发）。

认证并发回归额外连续运行 20 次：`20/20 PASS`。

### 静态检查与前端

```text
ruff check src tests scripts                         PASS
pnpm lint                                            PASS
node_modules/.bin/tsc.CMD --noEmit                  PASS
pnpm test:community                                  5/5 PASS
pnpm build                                           PASS, 55 routes generated
GitHub Actions YAML parse                            PASS
common secret-pattern scan                           PASS
```

### 容器与浏览器

```text
docker compose build api                             PASS
docker compose up -d --no-build --force-recreate api PASS
scripts/e2e_role_workbench_g4.py                     17/17 PASS
docker compose ps                                    API/PostgreSQL/Redis/Worker healthy; Web up
recent API 500/Traceback scan                        NONE
```

- 最终 API 镜像 ID：`sha256:3577416d8f530107b9a260140615f532821a097dfa5c55d9c1887f1b4eec25dc`
- 验收 Web 镜像 ID：`sha256:9ce62928db3f3cd22fdad2386746876eaeeefe885eb6149e6ef7273c31178fdf`
- 端口仅绑定回环地址：Web `127.0.0.1:3000`，API `127.0.0.1:8000`

### 本地发布预演门禁

使用虚拟不可变镜像 ID、回环 URL 和非生产测试凭据执行：

```text
scripts/release_preflight.py --allow-loopback --allow-local-image-ids
status=passed, images_pinned=true, ownership_declared=true
```

该结果只证明预演配置校验器工作，不能替代外部预发布环境或生产就绪复审。

## 视觉复核

- 1440px 页面无横向溢出或卡片穿模。
- “当前身份”“工作台成熟度”“可用/尚未接入能力”和“能力边界”层级清晰。
- 买家截图中的订单、售后均显示为未接入，零值没有被包装成真实交易数据。
- 顶部导航、身份切换、受控身份申请仍保留既有视觉语言。
