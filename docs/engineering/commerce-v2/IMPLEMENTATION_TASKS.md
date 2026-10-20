# 实施任务

| ID | 任务 | 依赖 | 关键验收 |
|---|---|---|---|
| COM-101 | 扩展 Product、Category、Media、Variant、HeritageLink | M0 | 迁移往返，旧数据兼容 |
| COM-102 | 服务端 Catalog Search API | COM-101 | 分页/排序/过滤稳定，越权关闭 |
| COM-103 | 拆分 Commerce API Schema 与 Router | M0 | 不改变既有响应前先补契约测试 |
| COM-201 | 商城首页与主题策展 | COM-102 | loading/empty/error/success/响应式 |
| COM-202 | 商品详情与可信来源层 | COM-101 | 不把商家声明显示为权威认证 |
| COM-203 | 购物车/订单体验收口 | COM-201 | 重复提交、版本冲突、确认与恢复 |
| COM-301 | ShoppingConversation 持久化 | COM-102 | 账户隔离、版本、过期、幂等 |
| COM-302 | Catalog Tool + Recommendation Verifier | COM-301 | 不存在/下架/变价商品不可返回为可购 |
| COM-303 | DeepSeek 导购工作流 | COM-302 | 超时、限流、模型错误可降级 |
| COM-304 | AI 导购 UI | COM-303 | 主动欢迎克制，商品卡可比较，移动端不遮挡 |
| COM-305 | AI Eval 与费用证据 | COM-303 | 固定数据集、模型版本、延迟、Token 与失败率 |
| COM-401 | 商家目录运营工作台 | COM-101 | seller 资源隔离和批量操作确认 |
| COM-402 | 商家经营信号与 AI 草案 | COM-401 | 只读分析默认，写操作人工确认 |

串行主链：`101 → 102 → 201/202 → 301 → 302 → 303 → 304 → 305`。

