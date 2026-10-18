# HAHA Gate C3：学习成长中心

日期：2026-10-18（Asia/Shanghai）

状态：`CLOSED_INTERNAL_NON_PRODUCTION`。Gate C3 是完整平台升级的中间 Gate；本文是架构与验收契约，
不是 Production Candidate、Production Ready 或最终重大升级四报告。

## 1. 目标与边界

Gate C3 在 C1 的统一账户、learner 角色和用户中心之上建立服务端权威学习闭环：

```text
学习档案 -> 学习路径 -> 课程/知识节点 -> 进度 -> 知识卡
        -> 服务端测验 -> 每日任务 -> 连续学习 -> 幂等成就 -> 用户中心汇总
```

不新增账户、权限系统、微服务或本地事实源。社区 `want_to_learn` 仍归 C1 用户资产表所有，
学习中心只按当前 `user_id + workspace_id` 读取候选并可记录报名来源，不复制账户归属。

“AI 非遗老师”已接入真实 DeepSeek 模型，并只检索精确命中的版本化内部复核知识记录。无命中、
来源越界或提示词边界校验失败时服务端拒答。`reviewed_internal` 只表示仓库内部复核，不构成官方
认证；当前种子课程仍为 `demo_only`，不得解释为正式教学发布。

## 2. 架构决策 ADR-C3-001

在现有 FastAPI 模块化单体中新增 `haha_learning` 限界上下文，并复用：

- `haha_identity` 的持久化 learner grant，所有读写均由后端再次核验；
- `haha_user_center` 的账户资产和成长聚合；
- `SQLAlchemyCreatorRepository` / `SQLiteCreatorRepository` 适配方式；
- PostgreSQL + Alembic 迁移链和现有依赖注入；
- Next.js App Router、`ProductFrame`、状态组件与设计 token。

拒绝用 localStorage 保存学习事实，拒绝用前端传入角色决定授权，拒绝用静态聊天或模板回答冒充
AI 老师已接通。当前同步事务足以覆盖内部规模，没有容量证据支持新增队列或独立学习服务。

## 3. 领域对象与权威状态

- `LearningProfile`：时区、当前/最长连续学习、版本与更新时间。
- `LearningPath` / `LearningUnit`：版本化目录、来源、可信状态和必修顺序。
- `KnowledgeSource` / `KnowledgeCard`：主题、来源、来源版本、可信状态和卡片乐观锁版本。
- `PathEnrollment` / `LearningProgress`：账户报名与节点状态，按用户和工作空间隔离。
- `Quiz` / `QuizQuestion` / `QuizAttempt`：服务端判分；答题、题目、正确项、解释、来源与版本快照
  写入后不更新。
- `LearningEvent`：带幂等键的追加式真实学习事件。
- `DailyTask`：按账户、本地活动日期和事件类型聚合。
- `AchievementDefinition` / `AchievementGrant`：版本化规则与一次性授予记录，保留触发事件。
- `TutorInteraction`：问题、幂等指纹、处理状态、受控引用、模型请求 ID、Token、延迟、错误码和时间戳审计。

## 4. 核心不变量

1. learner 授权只接受持久化 active grant；查询参数或前端显示状态不能提权。
2. 所有个人状态同时按 `user_id + workspace_id` 隔离；路径目录按工作空间隔离。
3. 报名、完成节点、知识卡与测验写操作要求 8–200 字符幂等键。
4. 进度和知识卡以 `expected_version` 乐观锁防止旧页面覆盖；冲突返回 409。
5. 测验答案必须精确覆盖当前题目集合，分数由服务端计算，答题记录不可变。
6. 每日任务、连续学习和成就只在同一数据库事务内由计数学习事件推进。
7. 成就以 `(user_id, workspace_id, definition_id)` 唯一约束防止重复领取，并记录规则版本和触发事件。
8. 同一幂等请求只允许一个事务赢家。PostgreSQL 使用 `INSERT ... ON CONFLICT ... RETURNING`
   判断真实插入结果，不依赖驱动不稳定的 `rowcount`。
9. 路径必修节点全部完成时，报名状态在同一事务内变为 completed。
10. `Asia/Shanghai` 活动日期依赖显式 `tzdata` 运行依赖，容器不依赖宿主机时区文件。
11. AI 老师只使用精确实体命中的 `reviewed_internal` 记录；未知项目不调用模型，回答引用必须是检索集合的子集。
12. AI 请求先写 `pending`，再以条件更新落为 `completed` 或 `failed`；同一幂等键不能更换问题。

## 5. API 契约

- `GET /api/learning`
- `POST /api/learning/paths/{path_id}/enroll`
- `POST /api/learning/units/{unit_id}/complete`
- `PUT /api/learning/cards/{unit_id}`
- `POST /api/learning/quizzes/{quiz_id}/attempts`
- `POST /api/learning/tutor/questions`

错误语义：401 未认证；403 未获 learner 授权、跨账户来源或未报名；404 资源不存在；409 版本或状态
冲突；429 超过 24 小时账户请求限额；503 模型/知识库不可用；422 Header/Schema 不合法；服务内字段
语义校验返回 400。

## 6. 数据迁移与回滚

Alembic `20261016_0010` 从 `20261015_0009` 新增 14 张 C3 基础表；增量迁移
`20261018_0015` 从 `20261018_0014` 新增 `tutor_interactions`、状态约束、账户/工作空间查询索引和
幂等唯一约束，不修改 C1/C2 表或既有用户数据。首次访问按当前账户惰性创建学习档案和每日任务；
演示目录按工作空间幂等写入。

回滚按外键反序删除 C3 表。真实环境执行 downgrade 前必须确认没有需保留的 C3 数据或已完成备份；
不能把应用回滚解释为自动删除学习数据。本轮已在隔离临时 PostgreSQL 数据库完成完整升级、
`downgrade 0014` 和再次 `upgrade head` 往返验证。

## 7. 前端状态与入口

- `/learning` 覆盖 loading、empty、error、permission、success 与 390/768/1440 响应式布局；
- 桌面主导航和移动底栏都有学习入口；移动底栏保持“首页 + 四大板块”共 5 个可触达项目；
- 页面显示路径、进度版本、来源可信状态、知识卡版本、服务端测验结果、每日任务和成就；
- 用户中心“今日”进入学习中心，“文化资产”展示服务端成长汇总；
- AI 老师在运行时探测凭据与知识库：可用时显示明确提问入口、引用与刷新历史，不可用时显示
  `BLOCKED`；演示目录和来源边界始终在主页面可见。

## 8. 验收状态

本地已执行并通过：

- Ruff、compileall、Next.js ESLint、社区契约测试与生产构建；
- 完整 pytest：138 passed，1 个上游弃用警告；
- 独立真实 PostgreSQL 集成：16 passed，包含并发幂等、AI 对话持久化与应用重建恢复；
- PostgreSQL API 闭环及 API 重启后恢复；
- 真实 Chrome 390/768/1440 视口、加入路径、完成节点、保存卡片、测验、刷新恢复、每日任务、
  成就、真实 AI 提问、引用、刷新恢复和用户中心同步，浏览器异常数为 0；
- Alembic 隔离数据库升级、回滚与再次升级。
- 受限真实 DeepSeek 评测：3/3，通过有来源回答、提示注入边界和未知项目零调用拒答，估算峰值成本
  `0.0006633 USD`。

浏览器截图与机器可读结果位于 `artifacts/e2e/learning-gate-c3-*`。GitHub CI 只有在本变更提交并推送
后才能形成远端证据，因此在此之前其状态为 `UNKNOWN`，不会伪报通过。

## 9. 已知边界

- AI 来源：当前为版本化内部复核记录；部分 URL 是主管机构入口页，不是条目级永久链接，正式教学发布前必须人工复核。
- AI 配额：24 小时账户限额适用于内部环境；高并发不同幂等键下的严格原子配额需在生产门禁增强。
- AI 可用性：部署未配置真实模型凭据或知识库失效时会自动回到 `BLOCKED`，不会降级为 Mock。
- 当前目录：内部机制验证，不是正式课程内容；正式内容治理、来源审核和发布流程仍待后续 Gate。
- 未执行公开发布、真实付费或 Production Readiness Gate。
