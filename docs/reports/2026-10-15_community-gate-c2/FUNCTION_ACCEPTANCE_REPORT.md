# Gate C2 功能验收报告

## 报告元数据

- 项目：HAHA 非遗图文脚本创作与视频内容社区平台
- 升级主题：Community Gate C2
- 报告状态：`COMPLETE`
- 验收时间：2026-10-15 20:09（Asia/Shanghai）
- 已测试实现提交：`55e0326b9c77ce1a17665afe1ad29fcaa3e15188`
- 分支：`main`
- 执行环境：Windows + Docker Desktop；Python 3.12.14；Node.js 24.20.0
- AI Eval：`N/A`，本轮未新增或修改模型能力、Prompt 或模型路由

## 结论

Gate C2-01 至 C2-10 在本轮定义的内部测试范围内均为 `PASS`。这里的 PASS 只表示相应命令或真实用户路径已执行并得到预期结果，不代表正式文化内容已上线，也不代表 Production Candidate。

基线提交为 `8a5f47c0f22771652360b316c2e97c95e4b630db`。最终实现提交已推送到 `origin/main`；GitHub CI 与 Pages 均在该精确 SHA 上完成并成功。

## 验收矩阵

| ID | 结果 | 执行证据 |
|---|---|---|
| C2-01 服务端 Feed/详情 | PASS | Docker API + PostgreSQL；Chrome 详情页断言 `detail_from_api=true` |
| C2-02 收藏/关注/历史权威 | PASS | HTTP 写入与重载；Chrome 收藏刷新后保持；跨用户所有权测试 |
| C2-03 评论/注释隔离 | PASS | 作者可删、其他用户 403；注释创建为 `pending` |
| C2-04 草稿恢复与版本冲突 | PASS | PostgreSQL 并发只允许一个版本更新；浏览器投稿跨刷新回读 |
| C2-05 禁止自审与审计 | PASS | 创作者自审 403；reviewer/admin 边界；7 条顺序审计事件 |
| C2-06 发布回流 | PASS | admin 发布后 Feed 出现内容，创作者收到 review 通知 |
| C2-07 本地档案迁移 | PASS | unit + HTTP + Chrome；预览、明确确认、指纹幂等、状态降级、本地副本保留 |
| C2-08 API 故障不回退 | PASS | Chrome 阻断 `/api/community/*` 后显示错误且内容卡为 0 |
| C2-09 既有能力无回归 | PASS | 完整 Python 96 passed；生产和静态 Web 构建通过 |
| C2-10 响应式无溢出 | PASS | Chrome 390/768/1024/1440，`scrollWidth == viewport` |

## 自动化测试

### Python 完整套件

命令：

```text
.venv\Scripts\python.exe -m pytest -q --basetemp=.test-artifacts\pytest-c2-final-20261015
```

最终复跑结果：`96 passed, 13 skipped, 1 warning in 4.59s`。

13 个跳过项是未向该命令导出 PostgreSQL 测试 URL 的集成组；随后在隔离 PostgreSQL 中全部执行通过，不能把 skip 本身当作 PASS。

### C2 聚焦回归

命令：

```text
.venv\Scripts\python.exe -m pytest tests/test_community_gate_c2.py -q
```

结果：`7 passed, 1 warning`。覆盖：工作区目录、排序契约、JWT fail-closed、互动所有权、投稿全状态机、迁移幂等与可信降级、状态/版本/审计事务回滚。

### 隔离 PostgreSQL

使用独立项目 `haha-c2-pgtest`、独立网络和独立 volume 迁移到 `20261015_0009` 后执行：

```text
HAHA_TEST_POSTGRES_URL=<isolated-loopback-url>
HAHA_JWT_SECRET=<test-only-secret>
.venv\Scripts\python.exe -m pytest tests/test_postgres_integration.py -q
```

结果：`13 passed in 5.40s`。临时容器、网络和 volume 已清理，开发数据库未被这次最终集成测试修改。

首次隔离运行因遗漏 `HAHA_JWT_SECRET` 得到 `12 passed / 1 failed`；失败点是测试配置读取密钥，不是功能断言。补齐测试配置后原组完整复跑通过。

### 静态质量与构建

- `ruff check src tests scripts`：PASS。
- `npm run lint`：PASS。
- `npx tsc --noEmit`：PASS。
- `pnpm test:community`：PASS，6/6；包括客户端分页上限与服务端 `limit <= 50` 契约。
- `npm run build`：PASS；55 个页面生成，BFF 动态路由存在。
- `npm run build:demo`：PASS；52 个静态页面生成，无 BFF 路由。

生产构建和静态构建为串行执行；静态构建脚本会临时移动 BFF 路由，不允许与生产构建并行。

## 真实 Docker 与 HTTP 验收

最终服务状态：

- API：healthy，`127.0.0.1:8000`
- Web：running，`127.0.0.1:3000`
- PostgreSQL：healthy，仅容器内 `5432`
- Redis：healthy，仅容器内 `6379`
- Worker：healthy
- Migrate：exit 0
- Alembic：`20261015_0009 (head)`
- `GET /ready`：`database=ok`、`redis=ok`

`scripts/e2e_community_gate_c2.py` 最终结果为 PASS，23/23 断言通过。报告：`artifacts/e2e/community-gate-c2-api/report.json`，最终本地复核时间 `2026-10-15T11:37:04+00:00`，真实投稿 ID 为 `submission_eab25641604f4da8bbf90da8e54dcc8a`。

脚本首次在持久化测试工作区错误假定内容总数必须恰好为 10；已有验收发布内容使总数大于 10。修正为校验 10 条 `demo_seed` 基线完整存在后，完整重跑 PASS。

## 真实 Chrome 验收

广域社区脚本 `scripts/e2e_community.py` 最终结果为 PASS：390/768/1024/1280/1440 五档首页、项目/人物/地图/专题/活动响应式页面、收藏刷新持久化、账户档案与搜索均通过；浏览器异常和失败 HTTP 响应均为 0。该复跑同时发现并修复了搜索 UI `limit=60` 与后端上限 50 不一致导致的真实 422。

`scripts/e2e_community_gate_c2_browser.py` 最终结果为 PASS：

- 390 / 768 / 1024 / 1440 四档视口各 23 张内容卡，无横向溢出。
- 服务端详情、收藏写入和刷新持久化通过。
- 文化账户档案通过。
- 本地档案迁移预览、提交、服务端回读通过。
- 本地 `verified/published` 不被信任，投稿回读为草稿；浏览器源副本仍存在。
- 创作者不能进入审核工作台。
- 素材元数据、投稿字段、关联关系、检查和 submitted 持久态通过。
- API 被阻断时不显示本地内容。
- 浏览器异常列表为空。

机器可读报告：`artifacts/e2e/community-gate-c2-browser/report.json`。截图目录：`artifacts/e2e/community-gate-c2-browser/`，包括四档首页、API 内容态、档案迁移态、投稿态和 API 故障态。

## GitHub Actions 真实 CI

- 被测 SHA：`55e0326b9c77ce1a17665afe1ad29fcaa3e15188`。
- `HAHA CI`：运行 `38730701104`，结论 `success`，完成时间 `2026-10-15T11:57:30Z`。链接：<https://github.com/duanxiao911/HAHA-/actions/runs/38730701104>。
- `community-e2e` Job `116407798966`：广域社区浏览器、C1 用户中心、C2 API、C2 浏览器四个验收步骤均为 `success`，证据构件上传成功。
- 其余 CI Job：`frontend`、`backend`、`container-build`、JWT `browser-session-e2e` 均为 `success`；后端包含 PostgreSQL 迁移、完整测试、AI 黄金集回归与 Redis/Dramatiq 边界。
- `Deploy demo to GitHub Pages`：运行 `38730701111`，build、deploy、部署后 smoke test 均为 `success`。链接：<https://github.com/duanxiao911/HAHA-/actions/runs/38730701111>。

证据链保留了一次非通过运行：初始实现提交 `bf39263` 的 CI `38725625196` 因浏览器在首次 API bootstrap 完成后、React 提交卡片前读取 DOM 而失败。最终提交增加条件等待，并在全新 CI 数据库上重跑全绿；没有把首次失败改写为 PASS。

## 认证证据

`tests/test_community_gate_c2.py:153` 使用真实登录签发 JWT 验证：

- 无凭据访问 C2 为 401。
- 仅伪造 `X-User-ID/X-Workspace-ID` 为 401。
- 有效 token 使用 token 内工作区，忽略伪造工作区头。
- viewer 不能创建投稿，为 403。

真实 Docker 浏览器验收运行在显式 opt-in、仅回环暴露的 development auth 环境；真实 staging/JWT 浏览器验收尚未执行，见风险报告。

## 已知测试告警

Python 套件有一条 Starlette/httpx 测试客户端弃用告警。它不影响本轮断言，但应在依赖升级窗口处理。

## Production Readiness Gate 判定

- Gate C2 功能验收：`PASS`。
- 本地 Docker 内部测试可用性：`PASS`。
- 独立 staging/JWT/HTTPS：`UNKNOWN`。
- 正式媒体发布、容量、限流、完整恢复和 Gate E 治理：`OPEN/UNKNOWN`。
- Production Candidate / Production Ready：`NOT DECLARED`。
