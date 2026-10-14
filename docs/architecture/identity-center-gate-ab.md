# HAHA 用户中心 Gate A/B 架构与契约

日期：2026-10-13

适用规范：

- `docs/governance/AI_FULLSTACK_SOP_V1.md`
- `docs/governance/HAHA_FOUR_MODULE_IDENTITY_SPEC_V1.md`

`SOURCE_MISSING`：两份规范提到的软件工程知识树、Project Architecture Scanner V2.0、
Production Readiness Gate V1.0、AI/Agent 原始知识体系和独立 UI/UX 原文未提供；本轮没有声称逐项
复核这些未取得的资料。

## 1. 目标和范围

本轮只实现四板块目标架构的 Gate A/B：同一账户的业务身份、申请、授权、上下文切换、身份工作台、
持久化任务和审计事件。不提前实现电商交易、AI 学习、正式审核后台或真实社区内容 API。

用户任务：同一账户开通多个身份，身份切换后进入相应工作上下文；刷新后保持状态；未授权身份、
管理员自授、跨用户任务操作和申请自审必须失败。

## 2. Architecture Scanner

| 模块 | 状态 | 决策 | 依据 |
|---|---|---|---|
| Next.js 正式前端 | IMPLEMENTED | KEEP | 已有统一社区框架与响应式设计系统 |
| FastAPI 模块化单体 | IMPLEMENTED | KEEP | 现有认证、可观测性和服务入口稳定 |
| users/workspaces/memberships | IMPLEMENTED | KEEP | 工作空间成员关系不等同于业务身份 |
| JWT + fail-closed | IMPLEMENTED | KEEP | 生产默认 JWT，开发认证显式开启 |
| PostgreSQL/Alembic | IMPLEMENTED | ADAPT | 新增身份中心表和迁移，不修改旧表语义 |
| Redis/Dramatiq | IMPLEMENTED | KEEP | Gate B 同步事务无需新增异步任务 |
| 文化档案 | PARTIAL | ADAPT | 当前社区增量仍是浏览器本地状态 |
| 多业务身份 | MISSING | ADD | 新建授权、申请、上下文和审计域 |
| 用户任务 | MISSING | ADD | 真实事件产生、服务端持久化、所有者隔离 |
| 电商/AI 学习工作台 | MISSING | DEFER | 页面明确标记后续 Gate，不提供伪功能 |

现有未提交的 SOP、`AGENTS.md` 和 README 修改均被保留并纳入本轮变更，没有覆盖用户资料。

## 3. ADR-IDENTITY-001：成员角色与业务身份分离

决策：保留 `memberships.role = owner/editor/viewer` 作为 Workspace 授权边界；新增
`role_grants.role = viewer/buyer/learner/creator/contributor/seller/reviewer/admin` 作为业务身份。

原因：身份切换是工作上下文，不应改变工作空间权限。后端不得信任前端提交的角色名称来授权资源。

替代方案：把所有身份写入 memberships；拒绝，因为会混淆组织权限和产品身份，并增加越权风险。

代价：资源 API 以后需要同时计算 Membership、RoleGrant、Scope 和 Ownership。

验证：未获得 admin grant 时切换 admin 返回 403；角色申请不能直接产生授权；申请人不能自审。

## 4. ADR-IDENTITY-002：继续采用模块化单体

决策：增加 `haha_identity` 领域和应用服务，由现有 repository adapter 提供 SQLite/PostgreSQL 实现，
不创建第二套登录系统、微服务或独立权限服务器。

原因：当前规模尚无独立部署证据；复用现有事务、迁移、日志和 CI 的成本更低。

## 5. 领域模型与不变量

- `UserProfile`：账户在一个 Workspace 下的展示资料和当前业务上下文。
- `RoleGrant`：服务端授予的业务身份；用户、Workspace、角色唯一。
- `RoleApplication`：卖家或知识贡献者申请；拥有明确审核状态。
- `IdentityTask`：由身份开通或审核结果产生的真实用户任务。
- `IdentityAuditEvent`：授权、申请、切换和任务完成的追加式审计证据。

不变量：

1. viewer、buyer 为基础身份；learner、creator 可自行开通。
2. contributor、seller 必须申请；reviewer、admin 不开放用户申请入口。
3. 申请不会自动授权；只有另一名 Workspace owner 可以作出当前审核决定。
4. 申请人不能审核自己的申请。
5. 只有 active grant 可以成为当前身份上下文。
6. 任务读取和完成必须同时匹配 user_id 与 workspace_id。
7. 重复完成任务不重复产生结果。
8. 重复开通同一身份不重复创建授权、任务或审计事件。

## 6. API 契约

所有端点首先执行现有 JWT/dev 身份认证和 Workspace Membership 解析。

| 方法 | 路径 | 行为 | 主要错误 |
|---|---|---|---|
| GET | `/api/identity/me` | 返回资料、有效身份、申请、任务和可用动作 | 401/403 |
| POST | `/api/identity/roles/{role}/activate` | 仅开通 learner/creator | 400/403 |
| POST | `/api/identity/role-applications` | 创建 seller/contributor 待审申请 | 400/403/409 |
| POST | `/api/identity/context` | 切换到已授权身份并持久化 | 400/403 |
| POST | `/api/identity/tasks/{id}/complete` | 所有者完成任务，幂等 | 404 |
| POST | `/api/identity/role-applications/{id}/decision` | Workspace owner 审核，禁止自审 | 400/403/404/409 |

身份上下文不是 Authorization 依据。后续创作、学习、交易和审核 API 必须根据持久化 grant、scope、
membership 和资源归属重新计算权限。

## 7. 数据库迁移

迁移：`20261013_0006_identity_growth_center.py`

新增：`user_profiles`、`role_grants`、`role_applications`、`identity_tasks`、
`identity_audit_events`。表包含外键、唯一约束、状态检查和所有者索引。

前向恢复：重新执行 `alembic upgrade head` 是幂等的。回滚函数只删除本迁移新增表，不修改旧
`users/workspaces/memberships`；生产回滚前仍必须备份，因为身份中心数据会被删除。

## 8. UI/UX 边界

用户已经确认身份总览、文化档案、身份工作台、消息与任务四视图。本轮复用现有产品 tokens、Header、
ProductFrame、状态组件和移动底栏，没有大规模重做四板块导航。电商、AI 学习、审核后台未闭环的入口
明确显示等待对应 Gate，不渲染可误解为已完成的按钮。

## 9. 验收映射

| Feature ID | 用户结果 | API/状态 | 自动化证据 | 状态 |
|---|---|---|---|---|
| ID-01 | 同账户拥有多个身份 | grants | unit + API + browser | PASS |
| ID-02 | 身份切换且刷新保持 | profile.active_role | API + browser reload | PASS |
| ID-03 | 未授权管理员身份被拒绝 | context validation | unit + API + real HTTP | PASS |
| ID-04 | 卖家申请后等待审核 | applications | API + browser | PASS |
| ID-05 | 另一审核人批准卖家身份 | application decision + grant | API + browser | PASS |
| ID-06 | 申请人不能自审 | actor invariant | unit + API + real HTTP | PASS |
| ID-07 | 用户任务隔离与幂等 | identity_tasks | unit + API + browser | PASS |
| ID-08 | PostgreSQL 审计证据 | audit events | migration + DB query | PASS |
| ID-09 | 跨设备真实文化档案 | community server API | 未实现 | PARTIAL |
| ID-10 | 分身份真实业务工作台 | content/learning/commerce services | 后续 Gate | PARTIAL |
