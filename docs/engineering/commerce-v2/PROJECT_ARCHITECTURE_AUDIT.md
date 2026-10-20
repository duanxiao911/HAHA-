# 非遗电商与 AI 导购升级：项目架构审计

日期：2026-10-20  
状态：`SCAN_COMPLETE / IMPLEMENTATION_NOT_STARTED`  
任务等级：Level 3 重大模块升级中的规划阶段

## 真实基线

- 分支 `main`，本地 HEAD `4ed50a3`，相对 `origin/main` 超前 1 个提交；工作区在扫描前干净。
- 远端最新 CI `39390932853` 对 `b4f643c` 为失败；已知唯一尾项在本地 `4ed50a3` 修复并通过本地浏览器验证，但按用户要求暂不推送，因此远端全绿仍为 `UNKNOWN`。
- 电商并非空白：现有 Gate D 已实现 PostgreSQL 交易沙盒，包括店铺、商品草稿与审核、库存、购物车、单店结算、内部沙盒支付、履约、售后、事件审计、版本冲突和幂等键。
- 本次重新执行 `python -m pytest -q tests/test_commerce_gate_d.py`：`4 passed, 1 warning`。
- DeepSeek 文本路由配置存在且 `text_ready=True`；图片模型未配置。配置存在不代表 AI 导购已实现或已经通过真实模型评测。

## 分层扫描

| 层 | 真实实现 | 结论 |
|---|---|---|
| Next.js | `/commerce` 单页包含商品、购物车、订单、卖家、审核视图；已有 loading/empty/error/permission/confirm 与响应式样式 | `ADAPT` |
| API | `/api/commerce` 下有 13 个读写入口，统一使用现有 Principal、用户和 Workspace | `KEEP + EXTEND` |
| Domain | Store/Product/Inventory/CartItem/Order/Payment/Fulfillment/AfterSale | `KEEP + EXTEND` |
| Service | 后端校验 seller/reviewer/admin、所有权、状态、版本和幂等 | `KEEP` |
| Repository | Protocol + SQLAlchemy Adapter，事务内结算和条件更新 | `KEEP` |
| PostgreSQL/Alembic | `0011` 建表，`0012` 补商品创建幂等；含外键、检查、唯一约束和索引 | `KEEP + FORWARD MIGRATE` |
| AI | 统一 Model Router 可调用 DeepSeek；学习老师已有持久化、限流与失败关闭范式 | `ADAPT`，不能直接复用学习 Prompt |
| 测试 | 单元、真实 PostgreSQL、真实 API、服务重启、Chrome 390/768/1440、CI 步骤均存在 | `KEEP + EXTEND` |

## 已实现与缺口

### 已实现，可保留

- 单一账户、buyer 默认能力与审核后 seller 权限。
- 商品发布审核和卖家不可自审。
- 购物车、库存原子扣减、重复结算/支付幂等。
- 买卖双方订单归属隔离、售后状态和审计事件。
- 明确的 `internal_sandbox` 边界，不伪装真实资金交易。

### 部分实现

- 商品只有标题、说明、单价、来源备注；没有媒体、类目、属性、SKU、工艺/产地关联和可信度结构。
- 搜索仅在浏览器内对当前快照做字符串过滤，不支持服务端查询、排序、分页或语义召回。
- 商家工作台只有建品、审核、库存和履约，没有经营概览、批量操作、客户问答或数据分析。
- 商品卡可购买，但没有商品详情页、收藏、比较、评价、地址和运费模型。

### 缺失

- AI 智能导购领域、会话、消息、工具契约、推荐证据和 Eval。
- 当季新品/主题策展、个性化但可解释的推荐、导购待机与恢复。
- 商品媒体、SKU/变体、类目/属性、服务端检索、推荐快照。
- 多店拆单、优惠、税费、真实支付退款、物流、结算和商家资质生产流程。

## 当前 UI 事实

现有页面是工程沙盒而非成熟商城：首页首屏被“边界说明”和大面积空白占据，商品只有一张文本卡；移动端基础导航可用，但缺少图片、商品详情、分类发现、季节主题和导购入口。因此需要重大信息架构调整，必须先确认预览再实施。

