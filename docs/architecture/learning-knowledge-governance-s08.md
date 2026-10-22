# S08 学习与知识治理增量架构

日期：2026-10-22（Asia/Shanghai）  
状态：`IMPLEMENTED_INTERNAL_NON_PRODUCTION`

## 目标与复用边界

S08 不重写 Gate C3，也不新增账户、导航板块或平行权限系统。它复用统一账户的默认 learner
能力、内部 `reviewer/admin` 授权、现有 FastAPI 模块化单体、PostgreSQL/Alembic 和学习中心页面，
补齐课程事件版本追溯与知识贡献审核隔离。

## 领域与状态契约

新增 `KnowledgeContribution`：主题、正文、来源标题、来源 URL、来源版本、状态、乐观锁版本、
审核说明、审核人和时间审计字段。公开提交直接进入 `submitted`，只允许转换为 `approved` 或
`rejected`。未经审核的记录不写入 `knowledge_sources`，也不进入 AI 老师的可信检索集合。

审核能力只接受服务端持久化的内部 `reviewer/admin` grant；公众前端不提供获取或切换内部身份的
入口，并禁止提交人自审。审核写入使用 `expected_version` 防止两个审核员覆盖彼此结论。

## 接口

- `POST /api/learning/contributions`：learner 提交，要求幂等键和完整来源。
- `GET /api/learning/contributions/review-queue`：内部审核队列。
- `POST /api/learning/contributions/{id}/review`：内部审核决定。

原有学习事件继续追加式持久化；课程完成事件的 `entity_version` 现指向课程节点版本，并在事件
负载保留节点、来源及测验版本，避免把个人进度版本误当课程版本。

## 迁移边界

`20261022_0020` 只新增 `knowledge_contributions` 表及账户查询、审核队列索引，不更新或删除既有
C1/C2/C3/D/E/F 数据。迁移可回滚；真实数据环境回滚前仍须备份并确认贡献记录处置方式。

## 验收证据

- Python 全回归：152 passed，22 skipped（未配置宿主 PostgreSQL 的条件跳过）。
- 隔离 PostgreSQL：22 passed，包含四线程相同幂等键并发只产生一条贡献记录。
- PostgreSQL 迁移：upgrade、downgrade 到 `0019`、再次 upgrade 均通过。
- Next.js：lint、契约测试、生产构建通过。
- 真实 API：学习闭环、贡献幂等、公众审核拒绝、服务重启恢复通过。
- 真实 Chrome：390/768/1440、贡献提交/刷新隔离、原 C3 闭环、AI 引用与用户中心同步通过，
  浏览器异常为 0。

本阶段不是 Production Candidate 或 Production Ready；正式权威知识入库仍需要条目级来源审核、
版权/授权确认和内容发布责任人。
