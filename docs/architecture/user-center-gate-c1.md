# HAHA 用户中心 Gate C1 架构、契约与验收基线

日期：2026-10-13（Asia/Shanghai）

状态：IMPLEMENTATION BASELINE

## 1. 目标

把 `/identity` 从以身份切换为主的页面升级为公共账户中枢，形成以下真实闭环：

1. 用户从社区内容执行收藏、想学、稍后看、关注或观看。
2. 操作经 FastAPI 认证与 Workspace Membership 校验。
3. PostgreSQL 按 `user_id + workspace_id` 持久化个人状态。
4. 用户中心“今日”和“文化资产”读取相同权威状态。
5. 用户可修改资料、历史/推荐/通知偏好，并清除自己的观看历史。
6. 其他用户不能读取或修改该账户的数据。

本轮不实现真实视频存储、电商订单、AI 学习模型或完整社区评论 API。

## 2. Architecture Scanner

| 模块 | 状态 | 决策 | 说明 |
|---|---|---|---|
| Next.js App Router | IMPLEMENTED | KEEP | 复用 ProductFrame、tokens、响应式框架 |
| 本地 CommunityAdapter | IMPLEMENTED | ADAPT | 保留内容目录、评论和投稿演示；个人资产写入真实 API |
| IdentityService | IMPLEMENTED | KEEP | 继续作为身份授权和当前工作上下文来源 |
| FastAPI 模块化单体 | IMPLEMENTED | KEEP | 增加 `haha_user_center` 领域，不拆微服务 |
| PostgreSQL/Alembic | IMPLEMENTED | ADAPT | 新增账户偏好、资产、关注、历史、通知和审计表 |
| SQLite adapter | IMPLEMENTED | ADAPT | 保持测试与本地开发契约一致 |
| Redis/Dramatiq | IMPLEMENTED | KEEP | 本轮同步用户操作不需要新队列 |
| 真实社区内容 API | MISSING | DEFER | 内容实体仍来自明确标记的演示目录 |
| 真实账户个人资产 | MISSING | ADD | 本轮核心 |
| 隐私控制 | PARTIAL | ADD | 历史、推荐、画像、通知和可见范围 |

`SOURCE_MISSING`：SOP 引用的软件工程知识树、Project Architecture Scanner V2.0、
Production Readiness Gate V1.0、AI/Agent 原始知识体系和独立 UI/UX 原文仍未取得。

## 3. ADR-UC-001：身份域与账户资产域分离

决策：`haha_identity` 管理角色、授权、申请和身份任务；`haha_user_center` 管理所有身份共享的
个人资料、偏好和文化资产。

原因：收藏、历史和通知属于账户，不应随当前业务身份切换；业务身份也不能成为读取他人资产的依据。

拒绝方案：继续把全部状态存入浏览器 localStorage。原因是不能跨设备、不能由服务端授权，也无法提供
可靠隐私删除和审计证据。

## 4. 领域与状态

- `UserCenterSettings`：简介、地区、资料可见范围、历史/推荐/通知开关。
- `LibraryItem`：bookmark、want_to_learn、watch_later 三类账户资产。
- `UserFollow`：用户关注的人物或创作者。
- `WatchHistoryItem`：最后观看时间、进度、时长和完成状态。
- `UserNotification`：由真实系统事件生成、可读和可删除的站内通知。
- `UserCenterAuditEvent`：资料、隐私、历史清理等敏感操作的追加审计。

不变量：

1. 所有查询和修改同时限定 `user_id` 与 `workspace_id`。
2. 同一用户、目标和资产类型唯一；重复写入为幂等更新。
3. 关闭观看历史后新观看不落库；已存在历史只在用户明确清除后删除。
4. 当前身份只是展示上下文，不改变个人资产所有权。
5. 画像默认关闭；购物行为不得在本轮进入文化兴趣画像。
6. 外部内容 ID 只作为演示目录引用，不被提升为可信知识事实。

## 5. API 契约

| 方法 | 路径 | 行为 |
|---|---|---|
| GET | `/api/user-center` | 返回身份、账户、偏好、资产、历史、通知与今日聚合 |
| PATCH | `/api/user-center/profile` | 更新显示名、简介、地区和资料可见范围 |
| PATCH | `/api/user-center/preferences` | 更新历史、推荐、画像和通知偏好 |
| PUT/DELETE | `/api/user-center/library/{kind}/{target_id}` | 幂等添加/移除个人资产 |
| PUT/DELETE | `/api/user-center/follows/{target_id}` | 幂等关注/取消关注 |
| PUT/DELETE | `/api/user-center/history/{content_id}` | 更新/移除观看进度 |
| DELETE | `/api/user-center/history` | 清除当前用户全部观看历史 |
| POST | `/api/user-center/notifications/{id}/read` | 幂等标记自己的通知已读 |
| DELETE | `/api/user-center/notifications/{id}` | 删除自己的通知 |

错误：未认证 401；非 Workspace 成员或越权 403；资源不属于当前用户时 404；非法类型或长度 400/422。

## 6. UI 信息架构

- 今日：继续观看、想学下一项、当前任务、资产摘要和当前身份快捷入口。
- 文化资产：收藏、想学、稍后看、关注和观看历史。
- 身份：保留授权、申请、切换和身份工作台入口。
- 消息与任务：真实服务端通知与身份任务。
- 账户设置：资料、可见范围、历史/推荐/画像/通知控制和清除历史。

身份切换降为账户能力之一，不再成为用户中心默认主内容。

## 7. Gate C1 验收

| ID | 用户结果 | 证据要求 |
|---|---|---|
| UC-01 | 社区收藏进入服务端文化资产 | API + DB + browser |
| UC-02 | 关注和观看进度刷新后保留 | API + DB + browser reload |
| UC-03 | 今日页给出真实继续项和任务 | browser + state assertion |
| UC-04 | 资料和隐私偏好可修改并恢复 | API + DB + browser reload |
| UC-05 | 关闭历史后不再产生新记录 | unit + API + real HTTP |
| UC-06 | 清除历史只影响当前用户 | unit + API + PostgreSQL |
| UC-07 | 通知已读、删除和用户隔离有效 | unit + API + browser |
| UC-08 | 原社区与身份链路无回归 | existing E2E suites |
| UC-09 | 390/768/1440 无横向溢出 | real Chrome screenshots |

