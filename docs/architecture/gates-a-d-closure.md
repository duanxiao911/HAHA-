# Gate A–D 收口矩阵

日期：2026-10-16（Asia/Shanghai）

状态：`BOUNDED_SCOPE_CLOSED`。该状态表示已冻结的内部平台范围具备真实实现与执行证据，不表示最初总规范的所有外部能力已经完成，也不表示 Production Candidate 或 Production Ready。

## 判定口径

本矩阵同时保留两种口径，防止用局部 Gate 的 PASS 覆盖总规范中的真实缺口：

- **已冻结内部范围**：各架构文档明确承诺且能够在当前仓库、PostgreSQL、真实 API 和浏览器环境中验证的范围。
- **最初总规范范围**：`HAHA_FOUR_MODULE_IDENTITY_SPEC_V1.md` 中包含正式媒体、真实 AI 教学、正式支付与生产工程的完整目标。

## 状态矩阵

| Gate | 已冻结内部范围 | 最初总规范口径 | 证据与边界 |
|---|---|---|---|
| A 架构与数据底座 | PASS | PASS | 统一 User/Workspace/Membership、业务身份、模块化单体、PostgreSQL/Alembic 与后端授权已建立。 |
| B 身份中心闭环 | PASS | PASS | 多身份、申请、独立审核、授权、切换、任务、审计和刷新恢复均有 API、数据库与浏览器证据。 |
| C 视频与 AI 学习 | PASS（C1/C2/C3 冻结范围） | PARTIAL / BLOCKED | 社区、创作者投稿、服务端学习、测验、任务、连续学习和成就已闭环；正式二进制媒体处理仍 OPEN，AI 非遗老师缺真实模型与可信检索而 BLOCKED。 |
| D 买卖家交易 | PASS（INTERNAL SANDBOX） | PASS（规范允许首期沙盒） | 卖家申请授权、商品独立审核、上下架、库存、订单、沙盒支付、履约、售后、通知、幂等与并发隔离已闭环；真实资金与商业合规不在沙盒 PASS 内。 |

## 本轮收口项

1. 商品 `listed ↔ delisted` 状态形成明确服务端与 UI 闭环；下架需要确认，退出买家目录但保留历史订单和审计。
2. 商品审核、订单、沙盒支付、履约与售后状态回流统一账户通知中心，通知键幂等。
3. 增加跨域权限测试：卖家申请被驳回后没有 seller grant，不能创建店铺或管理商品。
4. 保留商品来源 `seller_supplied_unverified`、课程 `demo_only` 与内部沙盒边界，不提升为权威事实或正式交易。

## 不能通过代码收口的项目

- **正式媒体链路：OPEN**。需要对象存储、MIME/恶意文件检测、FFprobe、转码、封面、CDN、删除与成本策略；当前 C2 只承诺素材元数据和内部投稿状态机。
- **AI 非遗老师：BLOCKED**。在真实模型和可信、版本化知识检索接口可用前，不得以模板、静态聊天或 Mock 冒充接通。
- **真实支付与退款：BLOCKED**。需要经营地区、商业主体、支付服务商、退款/结算责任、隐私和消费者保护方案。
- **Production Readiness：NOT STARTED AS GATE F**。安全审计、容量、备份恢复、监控告警、部署与回滚仍属于 Gate F。

## 本轮执行证据

- Ruff：`src tests scripts` 全部通过。
- Python 完整回归：`105 passed, 15 skipped, 1 warning`；15 项为主机命令未注入 PostgreSQL URL 的环境跳过。
- 真实 PostgreSQL：Gate D 最后一件库存并发结算测试通过。
- 真实 API：17 项交易、权限、幂等、履约、售后与账户通知断言通过；API 重启后的 6 项持久化断言通过。
- Next.js：ESLint、6 项社区契约测试和生产构建通过。
- 真实 Chrome：390/768/1440 无横向溢出；购物车 URL 状态、结算/支付确认、刷新恢复、卖家下架确认和下架结果均通过，浏览器异常为 0。
- 证据文件：`artifacts/e2e/commerce-gate-d-api/` 与 `artifacts/e2e/commerce-gate-d-browser/`。
- 远端 GitHub CI：本轮收口提交尚未推送，因此状态为 `UNKNOWN`，不能用本地结果代替。

因此，对外准确表述应为：**Gate A、B、D 已闭环；Gate C 的社区和非 AI 学习子范围已闭环，但原始 Gate C 总目标仍受正式媒体和真实 AI 教师阻断。前四 Gate 不能无条件标记为 100%。**
