# Gate C2 架构变更报告

## 交付元数据

- 项目：HAHA 非遗图文脚本创作与视频内容社区平台
- 升级主题：Community Gate C2
- 报告状态：`COMPLETE`
- 验收时间：2026-10-15 20:09（Asia/Shanghai）
- 已测试实现提交：`55e0326b9c77ce1a17665afe1ad29fcaa3e15188`
- 日期：2026-10-15（Asia/Shanghai）
- 基线分支：`main`
- 基线提交：`8a5f47c0f22771652360b316c2e97c95e4b630db`
- 验收时工作树：实现代码已提交并推送；本目录四份报告作为后续证据提交，不属于被测实现提交
- 环境：Windows，Python 3.12.14，Node.js 24.20.0，npm 11.19.0，Docker Compose 5.5.1
- 范围：Gate C2 浏览者与创作者服务端闭环
- 非声明：本报告不代表 Production Candidate 或 Production Ready

## 业务目标

把原先浏览器 `localStorage` 权威的社区演示，升级为由 FastAPI 与 PostgreSQL 管理的真实内部测试闭环：服务端目录、账户互动、评论、时间点知识注释、创作者投稿、审核状态、发布、通知与旧浏览器档案迁移。保留静态 Demo，但 API 故障时不允许静默回退为本地成功。

详细范围和验收契约见 `docs/architecture/community-gate-c2.md`。

## 变更前后

| 关注点 | 变更前 | Gate C2 后 |
|---|---|---|
| 社区权威状态 | `LocalCommunityAdapter` + `localStorage` | API 模式由 PostgreSQL 唯一权威；静态导出才使用本地适配器 |
| 内容目录 | 前端 seed | 服务端版本化 `demo_seed`，显式标注非权威演示来源 |
| 互动 | 浏览器收藏、关注、历史 | 目标存在性校验后写入账户资产或社区表 |
| 评论/知识注释 | 本地数据 | 工作区隔离、作者所有权；注释固定从 `pending` 开始 |
| 投稿 | 本地草稿与模拟状态 | 版本号、乐观锁、角色状态机、版本快照、追加式审计事件 |
| 审核/发布 | 可由本地状态模拟 | 禁止自审；reviewer 审核；仅 admin 发布；发布内容回流 Feed 和通知 |
| 本地档案迁移 | 无服务端入口 | 预览、明确确认、指纹幂等、可信状态降级、本地副本保留 |
| API 失败 | 可能继续本地体验 | 显式离线错误，禁止伪装服务端写入成功 |
| 搜索排序 | UI 有选项但服务端未执行 | `relevance/latest/popular/verified` 前后端契约贯通 |

## 代码与架构路径

### 领域与持久化

- `src/haha_community/domain.py`：领域错误、投稿状态机和不可变领域对象。
- `src/haha_community/service.py:66`：目录、互动、投稿、发布和迁移应用服务。
- `src/haha_community/service.py:730`：迁移预览；`src/haha_community/service.py:761`：幂等提交与可信状态降级。
- `src/haha_community/sqlalchemy_repository.py:448`：投稿当前态、版本快照和审计事件同事务写入。
- `src/haha_community/seed.py`：版本化内部演示目录，所有条目标记 `demo_seed`。
- `src/haha_user_center/service.py:362`：审核结果通知的确定性、幂等创建。

### 数据库

Alembic `20261015_0009` 只新增以下表，不修改 C1/G2/G3/G4 既有表：

- `community_entities`
- `community_respects`
- `community_comments`
- `community_annotations`
- `community_submissions`
- `community_submission_revisions`
- `community_submission_events`
- `community_import_receipts`

迁移文件：`migrations/versions/20261015_0009_community_gate_c2.py`；运行态实测为 `20261015_0009 (head)`。

### API

入口集中在 `src/haha_api/main.py:981` 至 `src/haha_api/main.py:1243`：

- 目录：bootstrap、feed、详情、搜索。
- 互动：反应、关注、历史、评论、知识注释。
- 投稿：列表、创建、详情、版本更新、状态迁移。
- 迁移：preview、commit。

身份与工作区仍由已有认证依赖解析；客户端不能通过 `X-Workspace-ID` 覆盖 JWT 内的工作区。

### Web

- `web/lib/community/api-adapter.ts:89`：API 适配器，失败不回退本地数据。
- `web/lib/community/provider.tsx`：只有显式 `NEXT_PUBLIC_DEMO_MODE=true` 才使用本地适配器。
- `web/app/profile/[id]/ProfileView.tsx:225`：浏览器文化档案检测、预览和确认迁移入口。
- `web/app/creator/submissions/new/SubmissionWizard.tsx`：服务端草稿和提交。
- `web/app/review/page.tsx`：reviewer/admin 角色边界与 admin 发布边界。
- `web/app/search/SearchExperience.tsx`：搜索排序契约接入。
- `web/lib/community/contract.ts`：统一客户端与 API 的分页上限；适配器在发起请求前执行边界归一化。

### CI 验收边界

- `.github/workflows/ci.yml` 的 `community-e2e` 现串行执行广域社区浏览器验收、C1 用户中心验收、C2 真实 API 验收和 C2 专项浏览器验收。
- C2 API 验收在 Compose 网络内使用应用镜像运行，通过公开 HTTP 调用业务 API；仅测试夹具通过数据库适配器授予 reviewer/admin，平台没有新增公共提权端点。
- 首次实现提交 `bf392632bd335eea3f1dcc5d081acc3a41b3f060` 暴露出新数据库首次 bootstrap 与 React 渲染之间的测试竞态。最终提交改为等待 API 内容实际进入 DOM，并将已不符合“禁止自审”架构的旧投稿验收职责移交给 C2 专项套件。

## 架构决策

采用现有模块化单体中的 `haha_community` 限界上下文，没有引入微服务、Kafka、Elasticsearch 或新缓存层。收藏、关注、历史和通知复用 User Center；C2 特有目录、评论、注释和投稿进入独立社区仓储。该方案满足当前内部测试规模，同时保留清晰端口以便后续替换检索或媒体基础设施。

## 数据迁移与恢复证据

- 迁移前备份：`artifacts/backups/2026-10-15_gate-c2_pre-migration.dump`（83,945 bytes）。
- SHA-256：`5846C107A5A4FB91F3285FD4E4B7AE912C77C61BB8B7929DD392F1B059A66A80`。
- 本轮曾误将会执行 `TRUNCATE ... CASCADE` 的 PostgreSQL 集成 fixture 指向开发数据库。发现后使用上述迁移前备份完成 downgrade、`pg_restore`、upgrade head，并验证关键记录计数及所有服务健康。
- 恢复命令成功和关键计数已验证；逐行语义等价比对未执行，因此完整数据等价性结论为 `UNKNOWN`。
- 最终 13 项 PostgreSQL 集成测试改在独立 Docker project 与独立 volume 中执行，结束后已删除该临时容器、网络和 volume。

## 回滚边界

- 应用回滚：可回到旧镜像，但 API 环境不得自动切换成本地可写演示。
- 数据库回滚：`0009` downgrade 会删除全部 C2 表，只能在确认无须保留 C2 数据或完成可验证备份后执行。
- 本地档案：迁移成功后仍保留浏览器副本，避免破坏性自动清理。

## 架构结论

Gate C2 范围内的服务端权威社区与创作者闭环已实现并完成真实环境验证。对象存储、媒体处理、正式文化目录、规模化搜索、统一 Gate E 审核后台和 Production Readiness 均不在本结论内。

远端证据：GitHub Actions `HAHA CI` 运行 `38730701104` 与 Pages 运行 `38730701111` 均在精确提交 `55e0326b9c77ce1a17665afe1ad29fcaa3e15188` 上成功；这只关闭 C2 的远端持续集成缺口，不扩大上述结论边界。

## 横向影响审查

- 安全/隐私：工作区和用户隔离、JWT 负向契约已测；正式 staging JWT 浏览器证据仍为 UNKNOWN。
- 性能/容量：当前最小充分架构适合内部规模；生产容量为 UNKNOWN。
- 可靠性/可观测性：健康、就绪、请求日志和审计事件已验证；告警与故障注入仍未验证。
- 成本：未新增外部服务或付费组件；正式媒体存储与转码成本为 UNKNOWN。
- 依赖/许可/IP：未新增 Python/Node 依赖；演示目录不构成正式文化数据授权结论。
