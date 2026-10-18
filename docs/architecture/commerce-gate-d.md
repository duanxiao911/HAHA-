# Gate D：非遗交易沙盒架构决策

状态：`CLOSED_INTERNAL_SANDBOX`。Gate C 已先行签署，Gate D 已完成本轮顺序复验；不代表真实交易或 Production Candidate。
日期：2026-10-18

## 目标与边界

Gate D 复用统一账户与 `buyer`、`seller`、`reviewer`、`admin` 业务身份，打通：

`卖家授权 → 店铺 → 商品草稿 → 独立审核 → 库存上架 → 购物车 → 单店结算 → 订单 → 内部沙盒支付 → 履约 → 售后`

本阶段是内部交易沙盒，不是生产电商系统：

- 不接真实支付、退款、结算或物流供应商；
- 不采集银行卡、支付口令或其他敏感支付凭证；
- `internal_sandbox` 只表示确定性的内部状态流转，不代表真实资金到账；
- 卖家商品说明与来源标记为 `seller_supplied_unverified`，审核通过不构成非遗事实、知识产权、商品资质或权威认证；
- 当前结算限同一店铺，避免在没有拆单、分账与多商户履约模型前伪装完整平台交易。

## 架构决策

沿用社区 Gate C2 的 bounded-context 适配模式：`haha_commerce` 拥有独立 Domain、Repository、Service 与 SQLAlchemy Adapter，但通过同一个 `DATABASE_URL` 使用现有 PostgreSQL，并由现有 Creator/Identity Repository 提供业务身份授权。没有第二套账户、权限或数据库技术栈。

HTTP 入口统一位于 `/api/commerce`。Next.js 页面位于 `/commerce`，通过现有身份工作台的能力卡进入；Gate D 不修改平台全局四入口信息架构，该结构调整留到 Gate E 预览确认。

## 核心状态

- Product：`draft → submitted → approved/rejected → listed ↔ delisted`；卖家不能审核自己的商品，下架保留历史订单与审计记录。
- Inventory：`available_qty`、`sold_qty`、`version`；结算以版本条件更新防止超卖。
- Order：`awaiting_sandbox_payment → paid → shipped → completed`，或支付前 `cancelled`，或支付后进入 `after_sales`。
- Payment：仅 `provider=internal_sandbox`、`status=authorized`；每个订单一条，账户 + 工作空间 + 幂等键唯一。
- Fulfillment：`shipped → delivered`。
- AfterSale：`requested → approved/rejected`；只记录售后决定，不触发真实退款。

## 事务、幂等与并发

- 结算在单一数据库事务内读取购物车、校验同店、校验商品与库存、条件扣减库存、生成订单快照、清空购物车并写入事件。
- `buyer_user_id + workspace_id + checkout_key` 保证重复结算返回同一订单。
- `seller_user_id + workspace_id + creation_key` 保证网络重试不会生成重复商品草稿；同一键复用不同内容返回冲突。
- 沙盒支付以账户 + 工作空间 + 幂等键去重；同一键用于其他订单会冲突。
- 并发使用同一结算或支付幂等键时，数据库唯一约束只允许一个事务赢家，其余请求读取并重放赢家；不会重复扣库存或生成支付记录。
- 商品、库存、购物车、订单、履约与售后使用显式版本；陈旧版本返回 409。
- 未支付订单取消时，在同一事务内恢复库存。
- 发货、确认收货和售后申请都检查条件更新影响行数；并发输家返回 409，事务整体回滚，不落半完成记录。
- 订单查询按买家或卖家归属过滤；支付、收货、履约和售后再次执行服务端所有权校验。
- `commerce_events` 保存关键状态变化的不可变审计事件。
- 商品审核、订单、履约与售后变化以稳定幂等键回流统一账户通知中心，重复请求不重复生成通知。

## 数据迁移

Alembic `20261016_0011` 新增 `commerce_*` 表、唯一约束、状态检查和主要查询索引；兼容迁移 `20261016_0012` 为商品创建补充幂等键，对已有草稿按主键生成唯一 legacy 键后再收紧非空与唯一约束。基础 `buyer` 身份仍由统一身份服务幂等补齐，卖家需既有审核授权。降级按版本逆序移除新增约束/字段或 Gate D 新表，不修改 C3 及以前数据。

## 验收门禁

1. 非 seller 不能建店、建商品、改库存或履约。
2. 非 reviewer/admin 不能审核，卖家不能自审。
3. 买家只能操作自己的购物车、订单、收货与售后。
4. 重复结算和重复沙盒支付不产生重复记录。
5. PostgreSQL 并发购买最后一件库存时只允许一个订单成功。
6. API 重启后商品、库存、订单、支付、履约与售后状态仍存在。
7. 页面覆盖 loading、empty、error、permission、success、确认对话框与 390/768/1440 响应式视口。
8. PostgreSQL 隔离库完成全量 `upgrade head → downgrade 0011 → upgrade head` 往返验证，最终为 `0015 (head)`。
9. 被驳回的卖家申请不产生 seller grant，不能创建店铺；卖家下架后商品立即退出买家目录，并可显式重新上架。

## 2026-10-18 顺序复验结果

- 完整 pytest：`139 passed, 1 warning`；Gate D 聚焦服务测试 `4 passed`。
- PostgreSQL：库存竞争与同结算/支付幂等键并发共 `2 passed`；同键并发只产生一个订单和一个支付记录。
- 真实 API：18 项交易断言通过，新增取消订单后库存与已售数量原子恢复；API 重启后 6 项状态恢复断言通过。
- Next.js：ESLint、既有社区/平台壳契约与 57 路由生产构建通过。
- 真实 Chrome：390/768/1440 无横向溢出；目录搜索/无结果、数量 2 结算、沙盒支付、发货、收货、下架和刷新恢复通过，浏览器异常为 0。
- UX：常用视图按商品、购物车、订单排列；目录搜索与数量编辑处于预期位置；支付、取消、审核退回、发货、收货、售后决定和下架使用明确确认语义。
- 证据位于 `artifacts/e2e/commerce-gate-d-api/` 与 `artifacts/e2e/commerce-gate-d-browser/`。远端 CI 在本提交推送前为 `UNKNOWN`。

## 仍然阻断

真实支付、退款、分账、税务、物流接口、商家资质、消费者保护与生产风控均为 `BLOCKED`。在地区、经营主体、支付服务商、退款与结算规则明确并完成合规评审前，不得把本模块声明为 Production Candidate 或 Production Ready。
