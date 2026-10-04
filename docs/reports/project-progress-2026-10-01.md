# HAHA 项目进程报告

日期：2026-10-01

范围：Production Upgrade Phase A + Phase B

分支：`main`

## 1. 执行结论

Phase A 与 Phase B 计划内链路均已实现并取得真实运行证据：持久化身份与工作区、PostgreSQL、
Redis/Dramatiq Worker、备份恢复演练、失败任务与卡住任务治理、可观测性、JWT 暂存环境、
Next.js 前端、浏览器 E2E、离线 AI Eval、在线小预算 Eval、GitHub Actions CI 以及 API/Web
生产镜像构建均已通过。

本报告不把项目标记为 Production Candidate 或 Production Ready。正式上线仍需单独执行安全、
容量、外部暂存部署、告警值班和发布回滚门槛。

## 2. 当前生产架构

| 层 | 当前实现 |
|---|---|
| Web | Next.js 16，生产 standalone 镜像，非 root 运行 |
| API | FastAPI，JWT/工作区鉴权，结构化日志、健康与指标端点 |
| Domain | 独立 Python 领域服务、参数版本、Run、脚本版本和验证结果 |
| Database | PostgreSQL 17，SQLAlchemy，Alembic 5 个版本化迁移 |
| Async | Redis 8 + Dramatiq，租约、重复投递保护、重试、DLQ 与 Reconciler |
| AI | Provider-neutral Router；本地确定性模式；DeepSeek Flash/V4 Pro |
| Delivery | Docker Compose 暂存编排 + GitHub Actions CI |

原 Streamlit 工作台仍可作为旧 UI 使用，但不再承担生产运行外壳；生产依赖也不再默认安装
Streamlit。

## 3. Phase A 完成情况

| 工作项 | 结果 | 核心证据 |
|---|---|---|
| User / Workspace / Membership 持久化 | PASS | 身份、角色、工作区边界和越权拒绝测试 |
| PostgreSQL 真实集成与并发事务 | PASS | Alembic、唯一约束、并发 claim、幂等事务 |
| Redis / Dramatiq Worker | PASS | 真实消息投递、持久化 Run、重复投递单一完成者 |
| Backup / Restore Drill | PASS | 备份、清空、恢复和行数校验 |
| DLQ / Stuck Run Reconciler | PASS | 超限进入 failed_jobs；可恢复租约重新排队 |

详细 Evidence 位于 `docs/evidence/phase-a-*.md`。

## 4. Phase B 完成情况

| 工作项 | 结果 | 核心证据 |
|---|---|---|
| Observability | PASS | JSON 日志、request_id、`/health`、`/ready`、`/metrics` |
| CI | PASS | GitHub Actions run `36863124074` 三个作业全绿 |
| Staging | PASS | JWT、PostgreSQL、Redis、Worker、API、Web 完整 Compose 启动 |
| Browser E2E | PASS | B站/90秒/16:9/纪录片与最终内容一致，浏览器异常 0 |
| Offline AI Eval | PASS | Golden Dataset 10/10，pass rate 1.0 |
| Live AI Eval | PASS | 2/2；Flash 与 V4 Pro 各一例；硬预算上限生效 |
| Container build | PASS | API 与 Web 均构建成功且以 `65532:65532` 非 root 运行 |

GitHub CI：<https://github.com/duanxiao911/HAHA-/actions/runs/36863124074>

## 5. Docker Hub EOF 处理结果

本机对 Docker Hub 的 Python/Node 基础镜像元数据请求持续出现 TLS `EOF`。最终处理方式：

1. API 与 Web 基础镜像改为固定 digest 的 Microsoft Artifact Registry Azure Linux 镜像；
2. Python 和 Node 包仓库改为可配置构建参数；
3. 本地使用可访问镜像完成生产镜像构建；
4. GitHub Actions 再次从干净 runner 构建两套镜像并通过。

该处理没有把 API 密钥、JWT 密钥或数据库密码写入镜像或 Git。

## 6. 测试与验收汇总

| 验收项 | 结果 |
|---|---|
| Ruff | PASS |
| Pytest | 57 passed |
| ESLint | PASS |
| Next.js production build | PASS |
| Alembic fresh migration | PASS，升级至 `20261001_0005` |
| PostgreSQL / Redis readiness | PASS |
| Real Redis/Dramatiq boundary | PASS |
| Full container browser E2E | PASS |
| API image build | PASS |
| Web image build | PASS |
| Secret pattern scan | PASS，97 个候选文件无命中 |

## 7. 在线 Eval 预算与结果

在线 Eval 限制为最多 2 次调用、每次最多 900 输出 tokens：

| 模型 | 结果 | 时延 | 输入 tokens | 输出 tokens |
|---|---|---:|---:|---:|
| `deepseek-flash` | PASS | 4,295 ms | 1,111 | 649 |
| `deepseek-v4-pro` | PASS | 6,253 ms | 1,119 | 418 |

合计输入 2,230、输出 1,067 tokens。按 2026-10-01 DeepSeek 公布的峰值、输入缓存未命中
[价格](https://api-docs.deepseek.com/quick_start/pricing/)进行保守估算，费用约为
**$0.00424446**。实际账单可能更低，最终以服务商账单为准。

## 8. 已知维护项与上线前门槛

以下内容不属于本轮 Phase B 功能失败，但应在 Production Candidate 评审前处理：

- GitHub runner 提示部分第三方 Action 内部仍使用 Node 20；当前 CI 已由 runner 强制 Node 24 并成功。
- 将暂存环境部署到真实域名与 TLS，而不是仅在本机 loopback 验证。
- 接入托管密钥服务，替代人工本地 secrets 文件。
- 完成依赖/容器安全扫描、SAST、权限审计和渗透测试。
- 完成负载、长稳、故障注入以及明确的 RTO/RPO 验收。
- 接入正式指标后端、告警路由、值班责任人和发布回滚演练。

## 9. 证据索引

- `docs/evidence/phase-b-summary.md`
- `docs/evidence/phase-b-03-staging.md`
- `docs/evidence/phase-b-04-browser-e2e.md`
- `docs/evidence/phase-b-05-ai-eval.md`
- `artifacts/e2e/phase-b-next-pipeline.png`（本地运行产物，不提交 Git）
- `artifacts/evals/phase-b-live-ai-eval.json`（本地运行产物，不提交 Git）

## 10. 状态判断

Phase A：完成。

Phase B：完成。

生产发布资格：尚未评定；需进入独立 Production Candidate Gate 后决定。
