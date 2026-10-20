# 数据与 API 迁移计划

## 迁移原则

- 只做前向、可回滚迁移，不重写 `0011/0012` 历史。
- 第一版新增字段先 nullable/default，完成回填和校验后再收紧约束。
- 既有 `commerce_order_items` 快照保持不变，历史订单不依赖当前商品状态。
- 商品媒体只保存受控对象键、类型、摘要和来源，不把大文件写入 PostgreSQL。

## 拟新增表

- `commerce_categories`
- `commerce_product_media`
- `commerce_product_variants`
- `commerce_product_heritage_links`
- `commerce_shopping_conversations`
- `commerce_shopping_messages`
- `commerce_recommendation_sets`
- `commerce_recommendation_items`
- `commerce_shopping_preferences`

## 索引/约束

- 类目 slug 唯一；SKU 在店铺范围唯一。
- 可售查询覆盖 `workspace_id + status + category_id + updated_at`。
- 会话和消息按 `user_id + workspace_id + updated_at` 索引。
- 推荐项外键到 recommendation set 和 product/variant，并保存生成时版本。
- 会话写入使用 idempotency key；版本冲突返回 409。

## API 版本边界

- 保留现有 `/api/commerce` 兼容快照直至新 UI 完成回归。
- 新增 `/api/commerce/catalog`、`/products/{id}`、`/advisor/conversations`、`/advisor/messages`。
- AI 消息响应仅包含验证后的展示模型和 `draft_actions`，不得直接创建订单或支付。

## 回滚

- 应用先停止写新字段，再降级数据库。
- 新表可逆删除前必须确认没有需要保留的用户会话证据。
- 已产生的订单、支付、履约和售后表不在本次回滚范围内。

