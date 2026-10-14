# G1 用户中心真实闭环｜架构变更报告

- 项目：HAHA 非遗图文脚本创作与视频内容社区平台
- 升级主题：User Center Gate C1 / G1
- 状态：COMPLETE
- 时间：2026-10-14（Asia/Shanghai）
- Git：`5a5fa4f06437ea2a02645faeb399b331303c2b9c`，分支 `main`
- 工作区：DIRTY；本次被测状态包含尚未提交的 Gate A/B 与 G1 变更，以上提交号不能单独重建全部被测代码。
- 执行环境：Windows 11 宿主机；Docker Desktop 29.8.1；PostgreSQL 17；Redis 8；FastAPI；Dramatiq；Next.js 16.3.6；真实 Chrome CDP。

## 变更前后

变更前，`/identity` 主要提供身份开通、申请、切换与任务，社区收藏、关注和观看历史仍以浏览器本地数据为主。变更后，在既有 `IdentityService` 旁新增独立的 `UserCenterService`，将账户资料、隐私偏好、文化资产、关注、观看历史、站内消息与审计写入服务端，并继续复用用户、工作空间与成员关系边界。

架构决策详见 [user-center-gate-c1.md](../../architecture/user-center-gate-c1.md)。采用“身份授权域 + 账户资产域”组合，而非把所有字段塞入身份表；没有引入新数据库、消息系统或状态管理框架。

## 真实修改路径

- Domain/Application：`src/haha_user_center/domain.py`、`service.py`、`repository.py`
- Persistence：`src/haha_core/repository.py`、`src/haha_core/sqlalchemy_repository.py`
- Migration：`migrations/versions/20261014_0007_user_center_gate_c1.py`
- API：`src/haha_api/main.py`
- Web：`web/lib/api.ts`、`web/app/identity/IdentityCenter.tsx`、`web/app/identity-center.css`、`web/app/content/[id]/ContentDetailView.tsx`
- Tests/CI：`tests/test_user_center.py`、`scripts/e2e_user_center_gate_c1.py`、`.github/workflows/ci.yml`

## API、数据与权限

新增 `/api/user-center` 聚合读取、资料和偏好 PATCH、文化资产/关注/历史 PUT+DELETE、消息已读与删除接口。所有资源键均由认证后的 `principal.user_id + workspace_id` 注入，不接受客户端伪造归属字段。站外 URL 被拒绝；通知读取要求资源归属匹配；历史关闭后写入返回空项且数据库不新增记录。

迁移新增 `user_center_settings`、`user_library_items`、`user_follows`、`user_watch_history`、`user_notifications`、`user_center_audit_events` 六类业务表（连同既有 `user_profiles` 构成 G1 账户数据）。唯一约束保证收藏、关注和观看记录幂等。

## 兼容、迁移与回滚

- 前向：Alembic `20261013_0006 -> 20261014_0007` 已在真实 PostgreSQL 成功执行。
- 兼容：保留本地 CommunityAdapter，用于尚未服务端化的评论、知识注释及演示数据；核心账户资产同时写入服务端。
- 回滚：迁移 downgrade 按审计、消息、历史、关注、资产、设置逆序删除。执行前必须备份；本轮未执行破坏性 downgrade，因此回滚数据恢复能力为 UNKNOWN。
- 恢复：文化资产写入幂等；页面刷新重新从聚合 API 恢复。

## 工程影响

- 安全/隐私：默认资料 `private`；历史、推荐、跨板块个性化、通知可独立关闭。PASS（代码与真实 API 证据）。
- 性能：聚合端点目前为多次小查询，适合内部测试规模；大用户资产分页尚未实现，容量结论 UNKNOWN。
- 可靠性：数据库唯一约束 + 服务幂等。PASS（重复写单测）。
- 可观测性：沿用 HTTP 指标与结构化日志；用户中心专用业务指标不足，见风险表。
- 成本：无新增外部服务与模型调用。
- AI 工作流：N/A，本次不修改模型、Prompt、Verifier 或在线 Eval。

