# HAHA Gate C2：真实内容账户与创作者闭环

日期：2026-10-15（Asia/Shanghai）

状态：IMPLEMENTED_AND_VALIDATED；验收证据见
`docs/reports/2026-10-15_community-gate-c2/FUNCTION_ACCEPTANCE_REPORT.md`。该状态只表示
Gate C2 范围已实现并通过本轮证据化验收，不是 Production Candidate 或 Production Ready 声明。

## 1. 目标与边界

Gate C2 把 Phase D 的浏览器本地社区闭环迁移为服务端权威的浏览者与创作者闭环：内容、项目、
人物、来源、事实、互动、评论、知识注释、投稿版本和审核状态由 FastAPI + PostgreSQL 管理，
并复用 C1 的账户资产、G2/G3 安全会话和 G4 多身份授权。

原 C2 验收不包含二进制媒体。2026-10-18 的 Gate C 收口增量已补齐单节点真实上传、持久卷、
发布后 HTTP Range 与浏览器播放，但仍不包含对象存储、恶意文件扫描、转码、CDN、AI 学习
（C3）、电商交易（D）或四模块统一审核后台（E）。

## 2. Architecture Scanner 决策

| 模块 | 当前状态 | C2 决策 |
|---|---|---|
| Next.js App Router / 设计系统 | 已运行 | KEEP |
| CommunityAdapter 契约 | 已隔离页面与存储 | ADAPT：新增 API adapter |
| LocalCommunityAdapter | localStorage 可写演示 | RESTRICT：只用于静态演示与离线契约测试 |
| FastAPI 模块化单体 | 已运行 | ADAPT：新增 `haha_community` 领域 |
| Identity / User Center / BFF 会话 | 已验证 | KEEP 并复用 |
| PostgreSQL / Alembic | 当前 head `20261014_0008` | ADAPT：新增 C2 表与索引 |
| Redis / Dramatiq | 已运行 | KEEP；C2 同步业务不新增队列 |
| Elasticsearch / Kafka / 微服务 | 不存在且当前无容量证据 | NOT ADDED |
| 媒体存储与播放 | 单节点文件适配器 + 独立持久卷 | ADAPT：真实上传/播放；生产级对象存储与处理继续 OPEN |

`SOURCE_MISSING`：统一 SOP 引用的外部知识树、Project Architecture Scanner V2.0 与独立
Production Readiness Gate 原文未随仓库提供。

## 3. 架构决策 ADR-C2-001

采用现有模块化单体内的新 `haha_community` bounded context（限界上下文），包含：

- Catalog：内容、项目、人物、地区、来源、事实和关系。
- Interaction：致意、评论、知识注释；收藏、想学、稍后看、关注和历史委托给 User Center。
- Submission：创作者草稿、不可变版本、确定性检查、提交和内容级审核。
- Import：旧浏览器文化档案的预览和幂等导入。

拒绝将社区实体继续作为不受服务端校验的字符串写入账户资产；拒绝在 API 失败时静默回退为
本地可写演示；拒绝为当前内部测试规模引入搜索集群或独立服务。

## 4. 权威状态与兼容模式

- Docker development / staging / JWT：`api` 模式，服务端是唯一业务权威。
- GitHub Pages 静态导出：`static_demo` 模式，保留显著演示标识，不承载真实账户。
- 正式 API 模式缺少后端时显示错误；不得把本地成功冒充服务端成功。
- C1 既有 `/api/user-center/*` 保持兼容；C2 API 先校验真实内容/人物，再写相同账户资产表。

## 5. 领域不变量

1. 业务记录按 `workspace_id` 隔离；个人记录同时按 `user_id` 隔离。
2. 只有 `published` 内容进入普通 Feed；草稿和审核数据不进入公开读取。
3. 收藏、想学、稍后看、关注和历史目标必须存在，不能再创建幽灵引用。
4. 评论只能由作者删除；知识注释创建后为 `pending`，普通用户不能提升为可信事实。
5. 创作者只能编辑自己的可编辑草稿；提交后当前版本不可静默覆盖。
6. 审核者必须拥有 reviewer/admin 授权，并且不能审核自己的投稿。
7. 所有投稿状态变化写追加式审计事件；非法跳转返回冲突。
8. 浏览器导入的 `verified/approved/published` 状态均不可信，必须降级为待核验或草稿。
9. 幂等写和迁移重试不得产生重复记录。
10. 只有服务端上传接口创建的 ready 素材可提交；未发布媒体对匿名读取返回 404。

## 6. 投稿状态机

```text
draft -> checking -> submitted -> reviewing
  ^         |             |          |
  |         v             v          +-> approved -> published
  +-- needs_revision <----+          +-> needs_revision
                                      +-> rejected

draft / needs_revision / rejected -> archived
```

- 创作者：创建、编辑、运行检查、提交、根据退回意见生成新版本、归档。
- reviewer/admin：领取审核、通过、退回、拒绝。
- admin：将已通过稿件发布；C2 不实现排期系统。

## 7. API 契约

读取：

- `GET /api/community/bootstrap`
- `GET /api/community/feed`
- `GET /api/community/contents/{content_id}`
- `GET /api/community/search`

浏览者写入：

- `PUT|DELETE /api/community/contents/{content_id}/reactions/{kind}`
- `PUT|DELETE /api/community/people/{person_id}/follow`
- `PUT|DELETE /api/community/contents/{content_id}/history`
- `POST /api/community/contents/{content_id}/comments`
- `DELETE /api/community/comments/{comment_id}`
- `POST /api/community/contents/{content_id}/annotations`
- `DELETE /api/community/annotations/{annotation_id}`

创作者与审核：

- `GET|POST /api/community/submissions`
- `GET|PATCH /api/community/submissions/{submission_id}`
- `POST /api/community/submissions/{submission_id}/transition`
- `PUT /api/community/submissions/{submission_id}/assets`
- `DELETE /api/community/submissions/{submission_id}/assets/{asset_id}`
- `GET /api/community/media/{asset_id}`（仅已发布，支持 Range）

迁移：

- `POST /api/community/imports/preview`
- `POST /api/community/imports/commit`

错误语义：401 未认证；403 无角色/跨域/自审；404 不存在或不可见；409 版本或状态冲突；
413 导入超限；422 Schema/引用非法；429 写频率超限（限流在后续垂直切片启用）。

## 8. 数据迁移、发布与回滚

- Alembic 迁移只新增 C2 表，不破坏 C1 数据。
- `20261018_0013` 新增 `community_media_assets`，`0014` 增加 kind/size/status 检查约束；降级删除媒体元数据表前，文件卷需先备份或按保留策略处理。
- 目录种子通过幂等服务端导入写入，所有条目标记 `demo_seed`，不会冒充权威名录。
- 本地档案导入先预览、再确认，以 payload 指纹和旧实体 ID 去重；成功前不删除浏览器副本。
- 应用回滚时显式切回静态演示仅用于演示站；真实账户环境不得自动回退。
- 数据库回滚只允许在确认没有需保留的 C2 数据或完成备份后执行。

## 9. Gate C2 验收

| ID | 用户结果 | 最低证据 |
|---|---|---|
| C2-01 | Feed/详情来自服务端目录 | API + PostgreSQL + browser |
| C2-02 | 收藏/关注/历史只有一个权威结果 | API + reload + second session |
| C2-03 | 评论/注释按作者隔离 | unit + API negative + browser |
| C2-04 | 草稿跨刷新恢复且并发旧版本冲突 | PostgreSQL + browser |
| C2-05 | 创作者不能自审，审核状态有审计 | API security + DB |
| C2-06 | 发布内容进入 Feed 并回流通知 | API + browser |
| C2-07 | 本地迁移幂等且不提升可信状态 | unit + API + browser |
| C2-08 | API 故障不静默回退本地写 | browser negative |
| C2-09 | C1/G2/G3/G4 与 AI 创作无回归 | existing suites |
| C2-10 | 390/768/1024/1440 无横向溢出 | real Chrome evidence |
