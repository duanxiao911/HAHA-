# HAHA P0 安全阻断修复报告（2026-10-09）

## 结论与边界

本轮仅修复独立 P0 安全阻断项，没有新增普通产品功能，没有重复 Phase A/B，且不构成
Production Candidate 声明。修复基线为本地 `main` 的 `5f9975b`；远端
`origin/main` 仍为 `828f066`，基线报告提交仍有 1 个本地提交尚未推送。本轮修复当前保持为
未提交工作区改动。

## 已复核并修复的问题

1. **认证 fail-open**
   - `src/haha_api/auth.py:31-62` 将缺省环境/认证改为 `production + jwt`；无 32 字符以上
     密钥时拒绝启动。
   - 开发头认证必须同时满足 `HAHA_ENVIRONMENT=development`、`HAHA_AUTH_MODE=dev`、
     `HAHA_ALLOW_DEV_AUTH=true`，预发布和生产即使设置 opt-in 也拒绝启动。
   - `compose.yaml:43-50` 明确本地 opt-in，并将 API 绑定到 `127.0.0.1:8000`；Web 同样仅
     绑定 `127.0.0.1:3000`。
   - `src/haha_api/main.py:191` 的 readiness 环境缺省也改为 production。

2. **DOCX Prompt 分隔符注入**
   - `src/haha_media/script_writer.py:350-384` 取消可由正文闭合的伪 XML 上下文。
   - 整个用户消息改为合法 JSON；可信知识位于 `trusted_context`，上传正文只位于
     `untrusted_input.asset_context` 的字符串值中。`</ASSET_CONTEXT>`、伪造的
     `<HERITAGE_FACT_CONTEXT>` 或角色声明都无法改变 JSON 结构。
   - 原有确定性 `fact_sources`、`fact_checks`、`shots` 和 `judgment` 架构保持不变。

3. **XML 实体膨胀**
   - `src/haha_media/asset_context.py:106-146` 使用 Expat 事件解析器，并显式拒绝 DTD、
     实体声明和外部实体，参数实体解析被关闭。
   - XML 输入在解析前已受 4 MiB `word/document.xml` 上限约束。

4. **ZIP 解压放大与资源耗尽**
   - `src/haha_media/asset_context.py:11-16` 定义压缩包、单条目、正文、总解压预算和压缩比
     上限。
   - `src/haha_media/asset_context.py:67-103` 在读取前检查中央目录元数据、重复正文、加密
     条目、单条目大小、累计大小和压缩比；正文通过 64 KiB 分块限量读取，并核对实际字节数。

5. **Verifier 事实接地**
   - `src/haha_core/verifier.py:12-61` 从公开字段提取非遗级别、年代/世纪、地域来源和传承人
     等关键事实原子。
   - 只允许这些原子出现在本次 `retrieval_trace.fact_chunks_used` 对应的已核验事实记录中；
     否则 `src/haha_core/verifier.py:97-105` 产生 `ungrounded_fact`，最终状态不能为 PASSED。

6. **自动化攻击回归**
   - 认证与越权配置：`tests/test_api.py:309-342`。
   - 实体、压缩比、正文条目、总解压预算：`tests/test_asset_context.py:36-84`。
   - Prompt 结构隔离：`tests/test_model_router.py:147-181`。
   - 未接地关键事实阻断：`tests/test_creator_service.py:282-300`。

## 验证结果

完整命令与结果保存在 `docs/evidence/p0-security-remediation-evidence-2026-10-09.md`。
关键结果为：P0 定向测试 53 passed；后端其余套件 77 passed、6 skipped、1 deselected；Ruff
通过；前端 ESLint 通过；Next.js production build 通过；开发与 staging Compose 配置校验通过。

## 剩余风险

- JSON 结构隔离降低了边界逃逸风险，但不能从理论上消除模型对不可信自然语言的语义服从；
  独立 Gate 前仍需针对真实在线模型运行攻击语料评测。
- 当前事实接地是确定性关键事实原子校验，不是完整命题蕴含证明；不含级别、年代、地域或身份
  标记的自由文本事实仍可能漏检。后续可在不改变本轮架构的前提下引入“声明—来源 ID”输出契约。
- 开发模式仍保留自动创建 owner 的既有便利行为，但只能三变量显式开启；若部署者主动覆盖本地端口
  绑定并开启该开关，风险仍由部署配置承担。
- 当前 JWT 为本地 HS256 验签边界，尚不包含企业身份提供方、密钥轮换、撤销或 JWKS 生命周期。
- 本机 pytest 临时目录存在既有 Windows ACL 异常，导致旧的单个 `tmp_path` 迁移测试无法运行；
  本轮相关测试及其余测试均已运行。该环境问题必须在独立 Gate 环境中复验。

## 独立 Production Readiness Gate 证据清单

- 干净提交和可追溯 diff；远端 CI 对该提交全绿。
- 默认无环境变量启动失败、缺密钥启动失败、development 未 opt-in 启动失败的日志证据。
- staging/production 尝试 `dev`（包括 opt-in=true）均启动失败的容器证据。
- 无凭据请求为 401，跨工作空间令牌为 403，合法 owner/editor/viewer 权限矩阵证据。
- 原始恶意 DOCX 样本、文件哈希、执行时间和峰值内存；DTD/实体、超大条目、高压缩比、总预算
  四类均被拒绝。
- 捕获的模型请求 JSON，证明恶意分隔符仅存在于 `untrusted_input.asset_context` 字符串中。
- Flash 与 V4 Pro 对抗性在线 Eval：分隔符、角色覆盖、伪事实源、间接提示注入均不得形成通过结果。
- `ungrounded_fact` 的正例、反例、中文年代/级别/地域/传承人边界样本和误报率记录。
- PostgreSQL、Redis、Dramatiq、JWT、浏览器 E2E 的真实 staging 回归。
- SBOM、依赖漏洞扫描、镜像摘要、密钥与日志脱敏检查、备份恢复和回滚演练。
- Gate 复审人签字及剩余风险接受记录；在这些证据完成前不得宣布 Production Candidate。
