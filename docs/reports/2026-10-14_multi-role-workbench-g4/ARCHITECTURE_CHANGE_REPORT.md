# G4 多身份工作台架构变更报告

## 元数据

- 日期：2026-10-14 17:19 +08:00
- 状态：`COMPLETE`（仅指 G4 既定范围）
- 分支：`main`
- 基线提交：`0e04230`（G1-G3 多身份用户中心基础）
- 实现提交：`72ad2cee28eaa4fade496a4b7d29f89a93dfb428`
- 环境：Windows 11 + Docker Desktop；Python 3.12；Next.js 16.3.6；PostgreSQL 17；Redis 8；JWT 模式
- Production Candidate：`NO`，本报告不构成生产候选或生产发布授权

## 业务目标

把用户中心从“只能切换身份”升级为服务端权威的多身份工作台。当前身份需要展示真实可用能力、
持久化资源和明确的能力边界，同时为后续视频社区、AI 学习、电商和统一审核垂直切片建立稳定契约。

本轮不接入真实模型 API，不建立商品/订单/支付领域，不新增普通产品模块，也不伪造尚不存在的交易、
学习或审核数据。

## Architecture Scanner 结论

| 现有资产 | 决策 | 原因 |
|---|---|---|
| FastAPI 模块化单体 | `KEEP + ADAPT` | 已有身份、用户中心和创作服务，无需拆微服务 |
| `IdentityService` | `KEEP` | 服务端授权、申请和身份切换已经持久化 |
| `UserCenterService` | `KEEP` | 收藏、想学、历史、通知和任务可作为真实投影来源 |
| Creator Repository | `ADAPT` | 补充按工作空间列出项目的只读端口 |
| Next.js 用户中心 | `ADAPT` | 新增当前身份工作台，不重做全站导航与设计系统 |
| AI 学习、电商、统一审核 | `BLOCKED` | 缺少真实领域模型/API，不用 Mock 冒充完成 |

详细决策见 `docs/architecture/multi-role-workbench-g4.md`。

## 变更前后

### 变更前

```text
Identity API -> RoleGrant / UserProfile -> 身份切换 UI
User Center  -> 收藏 / 历史 / 通知       -> 通用账户页面
Creator API  -> Project / Run           -> 独立创作入口
```

身份切换与真实业务资源之间没有统一投影，前端无法可靠回答“当前身份能做什么、数据来自哪里、哪些功能尚未接入”。

### 变更后

```text
GET /api/identity/workbench
        |
        v
WorkbenchService  (server-authoritative projection)
  |- UserProfile.active_role + active RoleGrant
  |- UserCenterService: library / history / tasks / applications
  `- CreatorRepository: workspace projects
        |
        v
Next.js IdentityCenter: metrics / capabilities / resources / boundary
```

接口不接受客户端角色覆盖参数。即使请求附加 `?role=admin`，返回仍由服务端保存的当前身份决定；
当前角色没有有效授权时返回 403，形成 fail-closed 边界。

## 主要代码路径

| 路径 | 变化 |
|---|---|
| `src/haha_workbench/domain.py` | 定义工作台成熟度和能力状态 |
| `src/haha_workbench/service.py` | 聚合当前身份、真实指标、资源、任务及边界 |
| `src/haha_workbench/repository.py` | 最小只读仓储端口 |
| `src/haha_api/main.py` | 新增 `GET /api/identity/workbench` |
| `src/haha_core/repository.py` | SQLite 项目列表；认证并发锁重试 |
| `src/haha_core/sqlalchemy_repository.py` | 项目列表；PostgreSQL/SQLite 原子 UPSERT |
| `web/lib/api.ts` | 工作台响应类型与 API 客户端 |
| `web/app/identity/IdentityCenter.tsx` | 当前身份工作台 UI 与并行数据加载 |
| `web/app/identity-center.css` | 工作台卡片、指标、资源与响应式布局 |
| `scripts/e2e_role_workbench_g4.py` | JWT/PostgreSQL/Chrome 真实闭环验收 |

## 数据与并发决策

- 无数据库迁移，无新增表。
- `user_profiles`、`user_center_settings`、`role_grants`、`user_notifications` 的首次初始化/保存改为
  PostgreSQL 与 SQLite 原子 `INSERT ... ON CONFLICT`，消除并行请求的“先查后插”竞态。
- SQLite 共享内存认证测试适配器为刷新令牌轮换和认证审计写入增加同一把锁与有限锁重试；
  刷新令牌仍通过哈希条件更新保证只能成功消费一次。
- 真实 E2E 曾先后发现 `role_grants`、`user_center_settings` 并发唯一键冲突以及通知 UPSERT 字段错误，
  均已修复并用全新账户重跑。

## 回滚

1. 回退实现提交 `72ad2ce`。
2. 移除工作台 API、前端投影和 `list_projects` 只读端口。
3. 不需要回滚数据库结构或删除既有用户数据。
4. 身份、账户、项目、收藏、历史和通知数据继续与 G3 兼容。
