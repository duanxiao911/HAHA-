# HAHA Gate C3：学习成长中心

日期：2026-10-16（Asia/Shanghai）

状态：IMPLEMENTED_AND_LOCALLY_VALIDATED。Gate C3 是完整平台升级的中间 Gate；本文是架构与验收契约，
不是 Production Candidate、Production Ready 或最终重大升级四报告。

## 1. 目标与边界

Gate C3 在 C1 的统一账户、learner 角色和用户中心之上建立服务端权威学习闭环：

```text
学习档案 -> 学习路径 -> 课程/知识节点 -> 进度 -> 知识卡
        -> 服务端测验 -> 每日任务 -> 连续学习 -> 幂等成就 -> 用户中心汇总
```

不新增账户、权限系统、微服务或本地事实源。社区 `want_to_learn` 仍归 C1 用户资产表所有，
学习中心只按当前 `user_id + workspace_id` 读取候选并可记录报名来源，不复制账户归属。

没有真实模型与可信知识检索接口，因此“AI 非遗老师”保持 `BLOCKED`。当前种子课程只验证来源、
版本和可信状态机制，统一标记 `demo_only`，不构成正式非遗事实、权威认证或教学结论。

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

## 5. API 契约

- `GET /api/learning`
- `POST /api/learning/paths/{path_id}/enroll`
- `POST /api/learning/units/{unit_id}/complete`
- `PUT /api/learning/cards/{unit_id}`
- `POST /api/learning/quizzes/{quiz_id}/attempts`

错误语义：401 未认证；403 未获 learner 授权、跨账户来源或未报名；404 资源不存在；409 版本或状态
冲突；422 Header/Schema 不合法；服务内字段语义校验返回 400。

## 6. 数据迁移与回滚

Alembic `20261016_0010` 从 `20261015_0009` 只新增 14 张 C3 表、唯一约束、检查约束、外键和查询
索引，不修改 C1/C2 表或既有用户数据。首次访问按当前账户惰性创建学习档案和每日任务；演示目录
按工作空间幂等写入。

回滚按外键反序删除 C3 表。真实环境执行 downgrade 前必须确认没有需保留的 C3 数据或已完成备份；
不能把应用回滚解释为自动删除学习数据。本轮已在隔离临时 PostgreSQL 数据库完成
`upgrade head -> downgrade 0009 -> upgrade head` 往返验证。

## 7. 前端状态与入口

- `/learning` 覆盖 loading、empty、error、permission、success 与 390/768/1440 响应式布局；
- 桌面主导航和移动底栏都有学习入口；移动底栏保持 6 个可触达项目；
- 页面显示路径、进度版本、来源可信状态、知识卡版本、服务端测验结果、每日任务和成就；
- 用户中心“今日”进入学习中心，“文化资产”展示服务端成长汇总；
- AI 老师边界和演示目录边界始终在主页面可见。

## 8. 验收状态

本地已执行并通过：

- Ruff、compileall、Next.js ESLint、社区契约测试与生产构建；
- 完整 pytest：101 passed，14 个 PostgreSQL 环境用例在主机套件中按配置跳过；
- 独立真实 PostgreSQL 集成：14 passed，包含并发幂等与持久化；
- PostgreSQL API 闭环及 API 重启后恢复；
- 真实 Chrome 390/768/1440 视口、加入路径、完成节点、保存卡片、测验、刷新恢复、每日任务、
  成就和用户中心同步，浏览器异常数为 0；
- Alembic 隔离数据库升级、回滚与再次升级。

浏览器截图与机器可读结果位于 `artifacts/e2e/learning-gate-c3-*`。GitHub CI 只有在本变更提交并推送
后才能形成远端证据，因此在此之前其状态为 `UNKNOWN`，不会伪报通过。

## 9. 已知边界

- AI 非遗老师：`BLOCKED`，缺少真实模型和可信知识检索接口。
- 当前目录：内部机制验证，不是正式课程内容；正式内容治理、来源审核和发布流程仍待后续 Gate。
- 未执行公开发布、真实付费或 Production Readiness Gate。
