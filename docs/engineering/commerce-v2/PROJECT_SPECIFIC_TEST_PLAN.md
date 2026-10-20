# 项目专属测试计划

| 层级 | 测试重点 | PASS 证据 |
|---|---|---|
| Unit | 状态机、过滤、推荐验证、敏感动作拦截 | pytest 完成日志 |
| Contract | Pydantic extra=forbid、错误码、兼容快照 | API 契约断言 |
| PostgreSQL | 迁移、索引、账户隔离、会话持久化 | 真实 PG 测试 |
| Concurrency | 最后一件库存、重复消息、重复加购/结算 | 单一赢家与无重复记录 |
| AI Eval | 需求澄清、无结果、价格变化、Prompt Injection、模型失败 | 固定集指标、模型/Token/延迟记录 |
| Browser E2E | 浏览→导购→比较→加购→结算→刷新→订单 | Chrome 390/768/1440 截图和断言 |
| Permission | 非 seller、跨商家、跨买家、公开 reviewer/admin | 后端 403/404，非仅隐藏按钮 |
| Recovery | API 重启、AI 超时、数据库回滚 | 状态恢复与降级路径 |
| Regression | C1/C2/C3、Gate D、平台壳、构建 | 既有套件无回归 |

AI V1 建议硬门槛：测试集中的推荐商品 ID 必须 100% 来自工具候选；不可售商品推荐为可购必须为 0；所有结算/支付请求必须有显式用户确认。质量偏好指标另以人工评审记录，不能用少量样本外推生产质量。

