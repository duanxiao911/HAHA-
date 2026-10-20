# 目标架构

```text
商城首页 / 商品详情 / 购物车 / 订单 / 商家工作台
                |              |
                |              +--> 确定性 Commerce API
                v
          AI 导购面板
                |
                v
      ShoppingAdvisorService
       |        |          |
       |        |          +--> Conversation Repository / Audit
       |        +--> Catalog Search Tool (服务端查询)
       +--> Model Router (DeepSeek)
                |
                v
      Recommendation Verifier
       - product/SKU 必须存在且可售
       - 价格/库存版本一致
       - 理由只能引用结构化字段
       - 敏感动作转换为待确认草案
```

## 新增最小领域对象

- `ProductCategory`：稳定类目树。
- `ProductMedia`：真实上传图片/视频及版权/来源说明。
- `ProductVariant`：SKU、属性、价格、状态和版本。
- `ProductHeritageLink`：商品与非遗主题/项目的关联及可信状态。
- `ShoppingConversation`：账户归属、状态、版本、更新时间和过期策略。
- `ShoppingMessage`：不可变消息、角色、模型证据和失败码。
- `RecommendationSet` / `RecommendationItem`：候选、理由、排序、商品版本快照。
- `ShoppingPreference`：仅保存用户显式同意的非敏感偏好，可查看和清除。

## AI 工作流

`欢迎/任务建议 → 意图提取 → 必要追问（最多 3 轮）→ 服务端召回 → 模型解释/组合 → 后端验证 → 商品卡 → 用户确认加购`

无候选、模型不可用、超时、限流或校验失败时，降级到普通商城搜索并说明原因。

