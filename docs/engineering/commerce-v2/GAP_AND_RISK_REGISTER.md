# 差距与风险登记

| ID | 证据/位置 | 差距 | 严重度 | 状态 |
|---|---|---|---|---|
| COM-G01 | `Product` 领域对象 | 无类目、媒体、SKU、属性、文化关联 | HIGH | OPEN |
| COM-G02 | `CommerceCenter.tsx` | 仅客户端字符串搜索，无分页排序 | HIGH | OPEN |
| COM-G03 | `/commerce` 截图 | 工程沙盒视觉层级，不是成熟商城发现体验 | HIGH | OPEN |
| COM-G04 | `haha_commerce` | 无导购会话、消息、推荐证据 | HIGH | OPEN |
| COM-G05 | Model Router | DeepSeek 可用但未为 commerce 声明任务类型 | HIGH | OPEN |
| COM-G06 | 商品来源字段 | 单一自由文本无法表达声明/审核/权威核验差异 | HIGH | OPEN |
| COM-G07 | 交易模型 | 无地址、运费、税费、优惠、多店拆单 | MEDIUM | DEFERRED_V1 |
| COM-G08 | 生产外部依赖 | 真实支付、退款、物流、结算与合规主体未确定 | CRITICAL | BLOCKED |
| COM-G09 | GitHub CI | 远端停留在 `b4f643c` 且红；本地修复未推送 | MEDIUM | DEFERRED_BY_USER |
| COM-G10 | AI 图片 | 图片模型 `image_ready=False` | LOW | N/A，商品媒体必须由商家真实上传 |

