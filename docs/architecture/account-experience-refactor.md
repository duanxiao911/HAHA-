# 统一账户体验重构

日期：2026-10-20
状态：IMPLEMENTED（受控开发/比赛演示范围，不代表 Production Ready）

## 目标

把注册、用户中心、专业工作台与内部权限恢复为符合用户心智模型的四层结构：

1. 一个邮箱密码账户承载个人资料与跨设备状态。
2. 浏览、学习、收藏、购物是账户默认能力，不是需要来回切换的身份。
3. 创作者可自行开通工作台；商家与知识贡献者需申请并审核。
4. 审核员和管理员是平台员工权限，只能由内部流程授予，不出现在公众申请或切换入口。

本次复用现有 users、workspaces、memberships、role_grants、FastAPI、SQLAlchemy、PostgreSQL、
Next.js BFF 和 HttpOnly Cookie 会话，不引入第二套账户或权限系统。

## 权限模型

| 层级 | 能力 | 获取方式 | 公众界面 |
|---|---|---|---|
| 统一账户 | viewer、buyer、learner | 服务端在有效 membership 上幂等授予 | 直接使用，不显示切换器 |
| 公开专业工作台 | creator | 用户确认后自行开通 | 可见 |
| 审核型专业工作台 | seller、contributor | 申请、他人审核、审计授予 | 可见 |
| 内部员工权限 | reviewer、admin | 内部邀请与最小授权 | 不可申请、不可公开切换 |

`active_role` 暂保留为专业工作台上下文的兼容投影，不作为资源授权事实源。普通能力和内部员工角色
不能经公众上下文切换 API 激活；所有资源 API 继续根据 membership、持久化 grant、scope 与资源归属
重新鉴权。

## 注册与会话

- `POST /api/auth/register` 接收 display_name、email 与 password，在单一事务中创建 user、个人
  workspace、owner membership、公开昵称资料和 credential，并立即签发与现有登录相同的可撤销会话。
- email 使用大小写无关的全局唯一索引；迁移在建索引前检查历史重复数据，有冲突即失败并要求人工处理。
- `/login` 不再要求用户输入 workspace；旧调用仍可选传 workspace_id，便于兼容内部脚本。
- Next.js `/api/session/register` 复用同源、请求体上限、HttpOnly/SameSite Cookie 与 CSRF 边界。
- `HAHA_SELF_REGISTRATION_ENABLED` 在生产默认 `false`；本地 Compose 可显式开启。

迁移 `20261020_0016_public_account_registration.py` 只增加大小写无关唯一索引；回滚只删除该索引，
不会删除已有账户。若历史凭据存在同邮箱多 Workspace，升级将明确中止，避免静默绑定错误账户。

## UI 信息架构

- 顶部头像菜单：用户中心、我的内容、专业工作台、消息与通知、设置与安全。
- 用户中心：概览、我的内容、按需出现的专业工作台、消息、设置。
- 首页：只做能力介绍与继续任务；不再引导普通用户在浏览者、学习者和买家之间转化。
- 注册页：不预选身份、不要求 Workspace；静态演示明确禁用真实注册。

## 已知生产阻断

- `BLOCKED`：邮箱所有权验证、找回密码、正式用户协议/隐私同意版本记录，尚无已批准供应商与法务文本。
- `BLOCKED`：公网级注册与登录的分布式速率限制、机器人防护、异常登录告警和 MFA。
- `BLOCKED`：内部员工邀请、离职回收、强制 MFA 与定期权限复核后台尚未形成完整闭环。
- 当前重复邮箱返回通用业务文案，但响应状态仍可能被用于账户枚举；正式开放前需结合邮件验证与限流统一处理。

因此本次可以用于受控开发和比赛演示，但不得标记为 Production Candidate 或 Production Ready。
