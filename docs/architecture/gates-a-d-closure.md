# Gate A–D 收口矩阵

日期：2026-10-18（Asia/Shanghai）

状态：`SEQUENTIAL_CLOSURE_REOPENED`。A、B 保持通过；C、D、E 按用户确认的依赖顺序重新收口。提前落地的 F 基础设施增量保留，但 F 已暂停，不得再称 A–E 已完成或已进入生产收口。

## 判定口径

本矩阵同时保留两种口径，防止用局部 Gate 的 PASS 覆盖总规范中的真实缺口：

- **已冻结内部范围**：各架构文档明确承诺且能够在当前仓库、PostgreSQL、真实 API 和浏览器环境中验证的范围。
- **最初总规范范围**：`HAHA_FOUR_MODULE_IDENTITY_SPEC_V1.md` 中包含正式媒体、真实 AI 教学、正式支付与生产工程的完整目标。

## 状态矩阵

| Gate | 已冻结内部范围 | 最初总规范口径 | 证据与边界 |
|---|---|---|---|
| A 架构与数据底座 | PASS | PASS | 统一 User/Workspace/Membership、业务身份、模块化单体、PostgreSQL/Alembic 与后端授权已建立。 |
| B 身份中心闭环 | PASS | PASS | 多身份、申请、独立审核、授权、切换、任务、审计和刷新恢复均有 API、数据库与浏览器证据。 |
| C 视频与 AI 学习 | PARTIAL / BLOCKED | PARTIAL / BLOCKED | 真实二进制上传、持久卷、发布后 Range 播放、Chrome 解码，以及服务端学习/成长均已通过；AI 非遗老师缺真实模型凭据，仍 BLOCKED。 |
| D 买卖家交易 | IMPLEMENTED，待顺序复验 | NOT CLOSED | 既有 INTERNAL SANDBOX 代码与证据保留；在 C 总 Gate 解阻前不越序签署 D 收口。真实资金与商业合规仍不属于沙盒能力。 |

## 2026-10-18 Gate C 媒体收口项

1. 新增服务端二进制媒体表、文件存储适配器、25 MiB 视频/15 MiB 图片上限、MIME 签名与 SHA-256 校验。
2. 上传以用户、Workspace、投稿版本和幂等键约束；数据库附件、投稿新版本与审计事件同事务写入。
3. 未发布素材不可公开读取；审核发布后内容实体引用真实媒体 URL，并支持 HTTP Range。
4. Docker 媒体卷独立持久化，由一次性 root 初始化服务调整所有权；API 继续以 UID 65532 运行。
5. Next.js 投稿页执行真实上传/删除，内容详情使用原生 video 控件；静态演示仍只登记本机元数据。

## 不能通过代码收口的项目

- **生产级媒体处理：OPEN（不再是功能链路缺失）**。当前本地/单节点真实上传、持久化和播放已通过；对象存储、恶意文件扫描、FFprobe 深度检查、转码、封面、CDN、配额与异地备份仍属于后续生产门禁。
- **AI 非遗老师：BLOCKED**。在真实模型和可信、版本化知识检索接口可用前，不得以模板、静态聊天或 Mock 冒充接通。
- **真实支付与退款：BLOCKED**。需要经营地区、商业主体、支付服务商、退款/结算责任、隐私和消费者保护方案。
- **Production Readiness：PAUSED**。已有提前实施的容量、数据库恢复、指标与 CI 增量保留；C、D、E 顺序收口前不继续推进或签署 F。

## 本轮执行证据

- Ruff：`src tests scripts` 通过。
- Python 社区回归：`8 passed`；包含上传权限、签名拒绝、幂等、发布可见性与 Range 读取。
- Python 完整回归：`129 passed, 1 warning`（注入测试专用 PostgreSQL、Redis 与 JWT 配置）；首次遗漏测试 JWT 密钥时为 `128 passed / 1 failed`，失败证据保留。
- PostgreSQL/Alembic：`20261018_0014 (head)`；旧数据保留，新表与媒体约束存在。
- 真实 API：26 项社区/媒体断言通过；真实 H.264 文件上传、发布和逐字节读取通过。
- Next.js：ESLint、6 项社区契约、4 项平台壳契约和生产构建通过。
- 真实 Chrome：390/768/1024/1440 无横向溢出；真实上传、已发布 H.264 解码播放、刷新、权限和 API 失败状态通过，浏览器异常为 0。
- 服务重启：API 重启后媒体仍返回 `200 video/mp4`，1683 字节与上传样本一致。
- 迁移回滚：在独立空 PostgreSQL 临时库执行媒体迁移 `upgrade → downgrade → upgrade` 通过；新增约束后会再次复验到 `0014`。
- AI 边界：运行时探测 `text_ready=false`；确定性黄金集 `10/10` 通过不能替代真实模型教学验收。
- 证据文件：`artifacts/e2e/community-gate-c2-api/` 与 `artifacts/e2e/community-gate-c2-browser/`。
- 远端 GitHub CI：当前提交尚未推送，因此为 `UNKNOWN`。

因此，对外准确表述应为：**Gate A、B 已闭环；Gate C 的真实媒体和非 AI 学习子范围已闭环，但原始 Gate C 总目标仍受真实 AI 教师阻断；D、E 保留既有实现但尚未按本轮顺序重新签署；F 已暂停。**
