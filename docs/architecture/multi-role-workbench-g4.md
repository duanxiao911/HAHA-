# G4 多身份工作台功能化：架构与验收契约

日期：2026-10-14

## 目标与范围

G4 把现有“身份切换”升级为服务端权威的当前身份工作台。工作台只聚合当前账户已经持久化的
身份授权、身份任务、文化资产、观看记录和创作项目；不提前实现 AI 学习对话、电商交易、知识
审核后台或平台管理后台。

本轮不改变四大板块的信息架构，不引入新技术栈，也不新增数据库表。它建立下一阶段垂直业务
闭环需要的统一能力状态契约。

## Architecture Scanner 决策

| 模块 | 当前状态 | G4 决策 |
|---|---|---|
| Next.js 用户中心 | 已有身份切换、资产、消息、设置 | ADAPT：加入当前身份工作台投影 |
| FastAPI 身份 API | 已有服务端授权、申请、切换 | ADAPT：新增只读工作台聚合接口 |
| Identity / User Center Service | 已持久化身份、任务、文化资产 | KEEP：作为工作台权威数据源 |
| Creator Project | 已有真实项目持久化 | ADAPT：补充工作空间项目列表端口 |
| AI 学习 | 尚无真实学习会话 API | BLOCKED：在工作台明确显示“待接入” |
| 电商 | 尚无商品、订单、支付领域 | BLOCKED：不展示虚构订单或经营数据 |
| 知识贡献 / 审核 | 有身份申请，没有知识稿件领域 | PARTIAL：显示真实申请/任务边界 |

## 架构决策

采用模块化单体内的只读 Projection Service（投影服务）：

```text
GET /api/identity/workbench
        |
        v
WorkbenchService
  |- IdentityService (当前授权身份、任务、申请)
  |- UserCenterService (文化资产、观看、通知)
  `- CreatorRepository (工作空间创作项目)
```

不接受客户端 `role` 参数。工作台角色只从服务端保存的 `profile.active_role` 推导，并再次验证其
对应授权仍然有效。因此“切换 UI”不能越权获取未授权工作台。

## API 契约

`GET /api/identity/workbench`

- 认证：与其他用户中心接口相同，必须通过 `resolve_membership`。
- 输入：无角色参数。
- 输出：
  - `role` / `label`：服务端当前身份。
  - `maturity`：`operational | partial | blocked`。
  - `metrics`：从真实持久状态计算的计数。
  - `capabilities`：`available | limited | blocked`，含原因和真实站内入口。
  - `resources`：当前身份可见的真实资产或创作项目。
  - `tasks`：仅当前身份的持久化任务。
  - `boundary_note`：未接入能力的明确边界。

## 权限与隐私

- 服务端忽略任何客户端自称角色；接口不存在角色覆盖参数。
- 当前身份必须存在有效 RoleGrant，否则接口 fail-closed。
- 文化资产按 `user_id + workspace_id` 隔离。
- 创作项目按已经通过 Membership 校验的 `workspace_id` 聚合。
- 响应不包含令牌、密码、内部 Prompt 或跨用户个人资料。

## 功能完整性验收

1. 默认浏览者工作台返回真实文化资产统计。
2. 学习者工作台返回真实“想学”资源，并将 AI 对话标记为 `blocked`。
3. 创作者工作台返回工作空间真实创作项目，并提供真实创作入口。
4. 买家/卖家不返回虚构订单、收入或库存，交易能力必须标记为 `blocked`。
5. 切换身份后再次读取工作台，角色与能力集合同步变化。
6. 未授权角色不能通过身份切换或工作台请求伪造。
7. SQLite 单元/API、PostgreSQL 集成、Next 类型/构建和真实浏览器闭环均有执行证据。

## 回滚

本轮无数据库迁移。回滚时移除工作台 API、前端投影和 `list_projects` 只读端口即可；既有身份、
账户、创作项目与会话数据不受影响。
