# Gate C1 用户中心收口｜架构变更报告

- 项目：HAHA 非遗图文脚本创作与视频内容社区平台
- 状态：COMPLETE（仅 Gate C1）；平台 Production Readiness：PARTIAL
- 时间：2026-10-15（Asia/Shanghai）
- Git：实现提交 `7523708`，`main`；执行测试时为与该提交代码等价的未提交工作树
- 环境：Windows 真实 Docker 栈，PostgreSQL 17、Redis 8、FastAPI、Dramatiq、Next.js 16、Headless Chrome

## 变更前后

变更前，文化资产虽已具备持久化基础，但身份管理仍占据主导航，关注、文化足迹、成长状态和消息删除没有形成完整可见闭环；并发首次访问可能在 `users` 插入处冲突。内容详情的观看历史 effect 又会因本地状态更新触发清理，导致 `busyAction` 永不释放。

变更后：

- `/identity` 固定为“今日、文化资产、消息与任务、设置”；身份切换进入顶部账户菜单。
- 专业工作台只对创作者、贡献者、卖家、审核员和管理员显示；浏览者、学习者、买家展示诚实能力边界。
- 文化资产统一展示服务端收藏、想学、稍后看、关注、观看历史及其真实聚合足迹。
- `ensure_identity` 使用 PostgreSQL 原子 insert-ignore，消除并发首次建号竞态。
- 欢迎消息只在首次创建设置时产生，删除后不会被 GET 重新生成。
- Docker 开发 Web 的公开 API 地址统一为 `127.0.0.1`；观看历史 effect 改用稳定字段依赖，不再永久锁住互动按钮。

## 决策与边界

继续采用 Next.js + FastAPI 模块化单体 + PostgreSQL，不增加微服务、队列或新数据存储。文化足迹由既有真实账户数据确定性聚合，不建立新的“伪成长系统”。学习路径、测验、成就和 AI 非遗老师明确留给 Gate C3；商品、订单与履约留给 Gate D；统一审核留给 Gate E。

关键路径：`web/app/identity/IdentityCenter.tsx`、`web/app/content/[id]/ContentDetailView.tsx`、`src/haha_user_center/service.py`、`src/haha_core/sqlalchemy_repository.py`、`compose.yaml`。

## 契约、权限与兼容性

API 路径未破坏性变更；`GET /api/user-center` 增加 `footprint`、`growth` 字段，旧客户端可忽略。所有账户数据继续以认证得到的 `user_id + workspace_id` 限定。通知删除、关注和资产操作保持所有者作用域。数据库无新迁移；回滚可恢复上述应用文件与 Web 镜像，现有数据保持兼容。

## 工程影响

- 安全/隐私：没有扩大角色权限；JWT 回归验证查询参数不能提权。
- 可靠性：首次建号从选择后插入改为冲突安全写入；欢迎消息不会复活。
- 性能：足迹为当前账户小集合聚合，未引入额外外部调用；容量上限仍需独立压测。
- 运维：开发浏览器端 API 回环地址确定化；正式 JWT 仍走同源 BFF。
- AI、成本、许可、知识产权：N/A，本轮未接入新模型、付费服务或依赖。

## 证据与恢复

真实 Docker 构建生成 55 个 Next.js 路由；API `/ready` 返回 database/redis `ok`，Web `/identity` 返回 200。功能证据详见同目录验收报告及 `artifacts/e2e/user-center-g1/`。独立备份恢复、容量和云端发布没有在本轮执行，保持 `UNKNOWN`，不据此宣布 Production Candidate。
