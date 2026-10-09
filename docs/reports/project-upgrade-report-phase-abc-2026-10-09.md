# HAHA 非遗图文脚本创作平台 Phase A/B/C 升级报告

报告日期：2026-10-09  
项目：HAHA 非遗图文脚本创作平台 V2  
代码分支：`main`  
报告范围：Production Upgrade Phase A、Phase B、Phase C  
当前提交：`828f066 feat: complete phase c5 release package`

## 1. 执行摘要

本轮升级已经完成 Phase A、Phase B、Phase C 的计划内工作，将项目从以 Streamlit 和本地状态
为主的原型，升级为具备正式 Web、持久化领域模型、异步任务、运行运维和发布回滚能力的
前后端分离平台。

主要结果：

- 建立 `Project → BriefVersion → Run → Verification → ScriptVersion` 权威数据链；
- 建立 User、Workspace、Membership 和 owner/editor/viewer 权限模型；
- 接入 PostgreSQL 17、SQLAlchemy、Alembic、Redis 8 和 Dramatiq Worker；
- 建立幂等创建、并发领取、租约、重试、失败任务、卡住任务治理和取消保护；
- 建立 FastAPI、JWT staging 边界、结构化日志、健康、就绪和指标端点；
- 建立 Next.js 16 正式前端、GitHub Pages 演示页和真实浏览器 E2E；
- 建立离线 Golden Dataset Eval 与 Flash/V4 Pro 小预算在线 Eval；
- 建立 GitHub Actions 真实 CI、API/Web 容器构建和非 root 运行；
- 建立认证 SSE 进度、运行取消和失败任务运维界面；
- 建立不可变镜像发布包、fail-closed 发布预检、发布 smoke、责任人制度和回滚演练。

Phase A、B、C 均已完成，但这不等于 Production Candidate 或 Production Ready。四项已展缓的
安全问题仍是发布阻断项，且尚未在第三方外部服务器完成真实 DNS/TLS 部署。

## 2. 升级前后对比

| 维度 | 升级前 | Phase C 完成后 |
|---|---|---|
| 前端 | Streamlit 为主 | Next.js 16 正式工作台；Streamlit 仅保留迁移兼容 |
| 业务状态 | 页面/Session 状态占比较高 | PostgreSQL 中的版本化领域对象为权威状态 |
| 任务执行 | 同步或本地执行 | Redis + Dramatiq 独立 Worker |
| 身份权限 | 本地开发身份为主 | JWT、持久化 Membership、工作区隔离和角色权限 |
| 运行生命周期 | 基础生成状态 | 幂等、领取、租约、心跳、重试、失败、取消、Reconciler |
| 运维能力 | 人工查看 | SSE 实时进度、取消、失败任务重试/处理 |
| 数据恢复 | 无正式证据 | PostgreSQL 备份恢复演练与 RPO/RTO 初始目标 |
| 质量验证 | 单元测试为主 | PostgreSQL/Redis/Worker/浏览器/AI Eval/CI 多层门禁 |
| 交付方式 | 本机启动 | 开发 Compose、JWT staging、不可变镜像 release Compose |
| 回滚能力 | 未形成流程 | 内容寻址镜像回滚、备份验证和独立回滚手册 |

## 3. 当前系统架构

| 层级 | 当前实现 |
|---|---|
| Public Web | Next.js 16，社区首页与 `/creator` 创作工作台 |
| API | FastAPI，JWT、workspace/role 鉴权、SSE、取消、失败任务接口 |
| Domain | Project、BriefVersion、Run、Verification、ScriptVersion |
| Database | PostgreSQL 17、SQLAlchemy、Alembic `20261001_0005` |
| Async | Redis 8、Dramatiq、租约/心跳、重复投递保护、限次重试 |
| AI | Provider-neutral Router、本地确定性模式、DeepSeek Flash/V4 Pro |
| Observability | JSON 日志、request ID、`/health`、`/ready`、`/metrics` |
| Delivery | Docker Compose、GitHub Actions、不可变镜像 release package |

核心数据链：

```text
Workspace + Membership
  └─ Project
      └─ BriefVersion（不可变）
          └─ Run（状态机、幂等键、尝试次数、租约）
              ├─ Retrieval / Model Evidence
              ├─ Independent Verification
              └─ ScriptVersion（不可变）
```

## 4. Phase A：生产核心与数据可靠性

Phase A 的目标是把原型的业务状态、身份边界和任务执行迁移到可持久化、可并发、可恢复的
生产形态。

### A1. 身份、工作区与成员权限

- 新增持久化 `users`、`workspaces`、`memberships`；
- Membership 使用 `(user_id, workspace_id)` 复合主键；
- 角色限定为 owner、editor、viewer；
- JWT 只用于证明身份，不直接信任 Token 中声明的角色；
- 实际权限从持久化 Membership 解析；
- 无 Membership 返回 403，JWT workspace 不可被请求头覆盖；
- Token 声称 owner、数据库记录为 viewer 时，仍按 viewer 限权。

初始验证：48 passed，Ruff 通过。

### A2. PostgreSQL 与并发事务

- PostgreSQL 17 + SQLAlchemy 作为生产数据层；
- Alembic 修复并建立完整新库迁移链；
- Run 幂等约束为 `(workspace_id, project_id, idempotency_key)`；
- 四个并发同幂等请求只创建一个 Run；
- 两个 Worker 不能同时领取同一 Run；
- 过期租约可回收，并推进 `lock_version`；
- ScriptVersion 插入后的强制失败会整体回滚。

真实 PostgreSQL 集成验证通过。

### A3. Redis 与 Dramatiq Worker

- Redis 8 启用 AOF；
- Dramatiq Worker 与 API 进程分离；
- 重复投递同一 Run 只有一个完成者和一个 ScriptVersion；
- Redis 重启后仍可继续投递和消费；
- PostgreSQL 保持系统记录权威，Redis 只承担消息边界。

### A4. 备份与恢复

- 使用 `pg_dump -Fc` 创建自定义格式备份；
- 恢复到独立数据库后校验 Alembic 版本和关键表行数；
- 恢复后的 API `/ready`、Run、ScriptVersion、Evidence 均可读取；
- 本地演练备份 21,435 bytes，备份与恢复约 2.264 秒；
- 初始目标：RPO 24 小时、RTO 4 小时、7 个日备份和 4 个周备份。

该本地耗时不是生产 SLA，生产仍需加密远端备份。

### A5. 失败任务与卡住任务治理

- 新增持久化 `failed_jobs`；
- 新增过期租约 Reconciler，并使用 PostgreSQL 行锁和 `SKIP LOCKED`；
- 可恢复任务进入 RETRYING，超限任务进入 FAILED；
- 失败原因持久化为 `lease_exhausted` 等机器可读字段；
- Reconciler 为显式、有界命令，不是无限循环；
- Alembic 最终升级到 `20261001_0005`。

Phase A 最终回归达到 53 passed，并完成真实 PostgreSQL、Redis、Worker 和恢复验证。

## 5. Phase B：产品化验证与交付链路

Phase B 的目标是补齐可观测性、正式前端、暂存环境、浏览器验收、AI 质量评测和托管 CI。

### B1. 可观测性

- 结构化 JSON 事件日志；
- API 到 Worker 的 request ID 关联；
- `/health` 进程健康端点；
- `/ready` PostgreSQL/Redis 依赖就绪端点；
- `/metrics` Prometheus 文本指标。

### B2. JWT Staging 与容器

- 完整 staging 栈：PostgreSQL、Redis、Alembic、FastAPI、Dramatiq、Next.js；
- staging 强制 JWT，匿名请求返回 401；
- API 与 Web 镜像使用数字用户 `65532:65532` 非 root 运行；
- 基础镜像使用固定 digest 的 Microsoft Artifact Registry Azure Linux 镜像；
- Python/Node 包仓库作为构建参数，解决本机 Docker Hub TLS EOF 问题；
- 密钥只在运行时注入，没有写入镜像或 Git。

### B3. Next.js 正式前端与浏览器 E2E

- Next.js 16 取代 Streamlit 作为正式 Web 外壳；
- 容器浏览器链路覆盖 `Next.js → FastAPI → Redis/Dramatiq → PostgreSQL`；
- B站、90 秒、16:9、纪录片参数与生成结果一致；
- 事实来源、独立验证和证据正常显示；
- 浏览器异常为 0。

### B4. AI Eval

离线 Eval：

- Golden Dataset 10/10；
- pass rate 1.0；
- 未知事实用例保持 fail-closed。

在线小预算 Eval：

| 模型 | 结果 | 时延 | 输入 Tokens | 输出 Tokens |
|---|---|---:|---:|---:|
| `deepseek-flash` | PASS | 4,295 ms | 1,111 | 649 |
| `deepseek-v4-pro` | PASS | 6,253 ms | 1,119 | 418 |

总计输入 2,230、输出 1,067 tokens；按当时公开峰值价格保守估算约 `$0.00424446`。

### B5. GitHub Actions

- 后端 Ruff、迁移、PostgreSQL 测试、Golden Eval、Redis/Dramatiq 边界；
- 前端依赖安装、ESLint 和 Next.js production build；
- API/Web 容器镜像构建；
- 首次 Phase B 托管 CI：run `36863124074`，三个作业全绿。

Phase B 收尾结果：57 passed、Ruff/ESLint/Next build 通过、完整容器与浏览器 E2E 通过。

## 6. Phase C：运行运维与发布回滚

Phase C 将已完成的生成链路升级为可观察、可控制、可处置、可发布、可回滚的产品面。

### C1. 认证 SSE 运行事件

- 新增 `GET /api/runs/{run_id}/events`；
- 复用 Membership 和 workspace 授权；
- 事件包含 event ID、状态、尝试次数、更新时间和安全错误字段；
- PASSED、FAILED、CANCELLED 发送终态事件并关闭；
- 非终态流限制为 1–30 秒，客户端按边界重连；
- 禁用代理缓冲和缓存。

### C2. 原子取消与 Worker 协作

- 新增 `POST /api/runs/{run_id}/cancel`；
- SQLite/PostgreSQL 均使用原子取消；
- 重复取消幂等，已完成/失败 Run 返回 409；
- 取消会清除 claim、heartbeat 和 lease；
- 旧 Worker 写入不能覆盖 CANCELLED；
- Worker 离线时取消、随后恢复投递，状态仍保持 CANCELLED 且不生成脚本。

### C3. 失败任务运维 API

- workspace 隔离的失败任务列表；
- viewer 可查看，owner/editor 可重试和标记解决；
- 重试原子消耗一次 attempt，并先解决当前失败记录再投递；
- 并发重试只能一个成功，另一个得到受控冲突；
- 最大三次尝试，重试后再次失败会重新打开记录；
- SQLite CI 锁竞争窗口在 2026-10-09 被发现并修复；
- 额外完成 500 次双线程竞争验证、完整本地回归和 6 项 PostgreSQL 集成测试。

### C4. Next.js 运维界面

- 使用带 Authorization 的 fetch-stream 消费 SSE，而不是受限的 `EventSource`；
- 支持 `Last-Event-ID` 重连，CORS 明确允许该请求头；
- 显示 PENDING、CLAIMED、RUNNING、RETRIEVING、GENERATING、VALIDATING、PASSED；
- 显示 attempt、取消按钮和终态提示；
- 新增失败任务列表、重新入队和标记已处理；
- GitHub Pages demo 与真实运维接口隔离。

真实 staging 浏览器验证覆盖：

1. 正常生成：SSE 生效，终态只补一次 Run GET，不再轮询；
2. Worker 停机取消：页面显示取消，Worker 重启后数据库仍为 CANCELLED；
3. 失败任务：真实失败记录可刷新、展示并标记处理；
4. 三种场景浏览器异常均为 0。

### C5. 外部 Staging 发布包与回滚

- 新增 `compose.release.yaml`；
- PostgreSQL、Redis、API、Worker、Web 均要求内容寻址镜像；
- 正式预检要求 `name@sha256:digest`，拒绝浮动标签；
- 要求 HTTPS Public URL、精确 CORS、回环容器绑定、足够长度密钥；
- 要求 Release、Rollback、Security、Data、On-call 五类责任人；
- 新增 release preflight、release smoke、发布手册、回滚手册和责任人规则；
- `/health` 增加 `release_id`，可确认当前实际运行版本；
- GitHub CI 每次验证 release preflight 和完整 Compose 渲染。

隔离发布与回滚演练：

- 候选发布的健康、就绪、Web、匿名拒绝、JWT 创建、request ID、CORS、SSE 重连均通过；
- 回滚前创建 18,447 bytes 自定义格式备份，`pg_restore -l` 校验通过；
- 停止 Worker 后切回上一版 C4 API/Web/Worker 镜像身份；
- API/Web 镜像身份、健康、就绪和已有数据保留均通过；
- 回滚后的真实浏览器生成通过，SSE 正常、终态 GET 1 次、浏览器异常 0；
- 演练容器、网络和数据卷随后全部清理。

Phase C 最终本地回归：68 passed、6 skipped；6 项 opt-in PostgreSQL 测试已在独立 PostgreSQL
环境和 GitHub CI 中执行。最终 CI run `37937267478` 的 backend、frontend、container-build
全部通过。

## 7. 三阶段交付状态

| 阶段 | 状态 | 最终成果 |
|---|---|---|
| Phase A | Complete | 生产数据链、身份权限、PostgreSQL、Redis/Worker、恢复和失败治理 |
| Phase B | Complete | 可观测性、正式 Web、staging、浏览器 E2E、AI Eval 和真实 CI |
| Phase C | Complete | SSE、取消、失败运维 UI、不可变发布包和回滚演练 |

当前 `main`：`828f066`。  
最新 C5 CI：<https://github.com/duanxiao911/HAHA-/actions/runs/37937267478>。

## 8. 已发现并关闭的重要缺陷

| 缺陷 | 处理结果 |
|---|---|
| Worker 继承 API HTTP health check，被误判 unhealthy | 为 Worker 增加独立进程健康检查 |
| SQLite 并发失败任务重试出现 table locked | Repository 串行化尝试消耗，Service 消除 TOCTOU |
| SSE 重连 `Last-Event-ID` 被 CORS 预检阻断 | CORS 允许该 Header，并增加契约测试 |
| 社区首页恢复后 E2E 仍访问 `/` | E2E 明确进入 `/creator` |
| Docker Hub Python/Node 元数据 TLS EOF | 固定 MCR digest，并允许配置包镜像源 |

## 9. 尚未完成与发布阻断项

以下四项安全问题已确认但按决策展缓，当前仍未修复：

1. 默认 `development + dev auth` 组合可能导致漏配环境时 fail-open，并允许任意开发身份成为
   workspace owner；
2. DOCX `asset_context` 可闭合伪 XML 分隔符并向模型 Prompt 注入伪造事实区段；
3. 不可信 DOCX XML 使用标准 ElementTree 解析，存在实体膨胀风险；
4. DOCX ZIP 条目缺少解压前大小和压缩比限制，存在 ZIP 放大风险。

其他尚未完成的外部条件：

- 尚未提供第三方 staging 主机、镜像仓库、域名和 TLS 权限；
- 正式 OIDC/组织身份提供方尚未替换过渡期 JWT issuer；
- 托管密钥服务、SAST/容器扫描、依赖扫描和渗透测试尚未形成最终证据；
- 负载、长稳、故障注入和正式告警值班尚未完成 Production Candidate 门禁；
- GitHub Actions 仍提示部分 Action 内部使用 Node 20，当前 runner 强制 Node 24 后 CI 可通过；
- Ubuntu runner 将迁移版本，需要后续兼容性观察。

因此当前状态只能表述为：Phase A/B/C 计划完成，发布基础设施和回滚程序已验证；不得表述为
Production Candidate 或 Production Ready。

## 10. 建议的下一阶段

下一阶段应首先关闭四项安全阻断问题，并形成独立安全证据：

1. 安全默认值改为 fail-closed，开发认证必须显式 opt-in；
2. 资产上下文改用结构化序列化或严格分隔符编码；
3. 使用 `defusedxml` 或等效安全解析器；
4. 在读取 DOCX 条目前校验解压尺寸、压缩比和总预算，并限量流式读取；
5. 在 verifier 中增加事实接地校验，避免模型字段携带无证据事实仍显示验收通过；
6. 补充恶意文件、Prompt 注入、权限接管和资源耗尽回归测试；
7. 安全门禁通过后，才进入独立 Production Candidate 评审。

## 11. 证据索引

- Phase A：`docs/evidence/phase-a-01-*` 至 `phase-a-05-*`
- Phase B：`docs/evidence/phase-b-summary.md`
- Phase B 浏览器：`docs/evidence/phase-b-04-browser-e2e.md`
- Phase B AI Eval：`docs/evidence/phase-b-05-ai-eval.md`
- Phase C 真实环境：`docs/evidence/phase-c-real-environment-validation.md`
- Phase C1–C5：`docs/evidence/phase-c-01-*` 至 `phase-c-05-*`
- 发布手册：`docs/operations/release-runbook.md`
- 回滚手册：`docs/operations/rollback-runbook.md`
- 责任人规则：`docs/operations/release-ownership.md`

## 12. 最终结论

Phase A、Phase B、Phase C 的计划内升级已经全部实现、验证、提交并通过 GitHub CI。平台已经
具备生产形态的核心数据链、异步执行、真实 Web、运行运维、发布预检和回滚能力。

项目下一步不应继续堆叠普通功能，而应优先解决四项安全阻断问题并完成外部环境、安全、容量
和告警门禁。只有这些独立门禁通过后，才能评估是否达到 Production Candidate。
