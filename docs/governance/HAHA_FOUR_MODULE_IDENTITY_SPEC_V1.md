# HAHA 非遗文化平台｜四大板块 × 多身份与成长中心全栈开发指令 V1.0

## 0. 项目任务

在 HAHA 现有代码库上，开发统一的多身份、多板块非遗文化平台。

目标产品由四个核心板块构成：

1. 视频社区（Video Community）
2. 非遗电商（Heritage Commerce）
3. AI 文化学习（AI Cultural Learning）
4. 用户中心·身份与文化成长空间（Identity & Growth Center）

一个用户使用同一账户，拥有多个经过授权的业务身份，可在身份工作台中切换任务上下文。

本任务要求实际开发、测试和交付，不只是生成设计文档。

## 1. 强制遵循既有开发 SOP

首先读取项目现有工程规范：

- 软件工程 × Python × Production Engineering 知识树
- Project Architecture Scanner V2.0
- Production Readiness Gate V1.0
- AI / Agent Engineering 知识体系
- UI/UX 设计规范
- AI 全栈应用开发统一 SOP V1.0

如果文件不可用，标记 SOURCE_MISSING，使用已知原则制定架构，不能冒充已经读取。

执行完整路径：

Requirements
→ Architecture Scanner
→ Architecture Decisions
→ Domain / State / API Contracts
→ UI/UX Preview
→ Implementation
→ Functional Integrity
→ AI Eval
→ Production Readiness
→ Delivery

先形成完整目标架构，再按真实依赖实施，不随意扩大范围。

## 2. 执行项目扫描

实际检查：

- Git 状态与项目入口
- Next.js 前端及页面
- FastAPI 后端
- 用户与 Workspace 数据
- Membership 和 JWT 认证
- PostgreSQL / Alembic
- Redis / Dramatiq
- 视频上传与内容数据
- AI 脚本创作能力
- 知识库与 AI Model Router
- 现有 UI 组件
- CI/CD、测试和部署
- 安全报告中的遗留缺陷

区分：

IMPLEMENTED / PARTIAL / MISSING / UNKNOWN。

输出 KEEP / ADAPT / REPLACE 矩阵。

不得因为旧报告提到某功能就直接认定当前版本已实现。

保留原有 HAHA 图文脚本创作与项目数据。

建立可恢复的 Git 开发基线，不覆盖未提交修改。

## 3. 架构原则

采用：

Next.js Frontend
↓
FastAPI Modular Monolith
↓
Domain / Application Services
↓
PostgreSQL + Redis / Dramatiq
↓
AI Models / Storage / External Providers

以现有项目为准，不强制替换已经稳定运行的技术栈。

禁止为多身份系统单独再造第二套用户登录系统。

禁止把每个身份拆成独立微服务。

不默认引入 Kubernetes、Kafka、Multi-Agent 或独立权限服务器。

只有证据证明复杂度必要时才升级。

## 4. 统一身份与权限域

建立以下逻辑对象：

User
UserProfile
RoleDefinition
RoleGrant
RoleApplication
Workspace
Membership
CreatorProfile
MerchantProfile
LearningProfile
PermissionPolicy
IdentityAuditEvent

基本约束：

- 一个 User ID。
- 一个用户可以拥有多个业务身份。
- 业务身份与 Workspace Membership 不能混为一谈。
- 权限具备业务范围或资源范围。
- 角色开通、审核、撤销具有明确状态。
- 身份切换不能自动提升权限。
- 所有权限由后端校验。
- 前端菜单隐藏不等于后端授权。

推荐角色开通流程：

普通账户：
自动具备基础浏览和买家能力。

学习者：
用户开通学习档案。

创作者：
开通创作者资料，创建创作空间。

知识贡献者：
用户申请或开通投稿，资料经过来源审核后才能成为可信知识。

卖家：
提交入驻申请，经过审核并满足经营要求后获得权限。

审核员：
平台内部授权，限定审核范围。

管理员：
仅由已有高权限管理员通过受控流程授予。

所有高权限操作写入审计记录。

必须阻止：

- 普通用户自行获得管理员权限。
- 卖家读取其他商家的经营数据。
- 用户读取别人的订单和收货地址。
- 审核员审核自己的作品。
- 前端伪造身份上下文绕过后端权限。

## 5. 平台共用领域服务

建立或复用以下服务边界：

Identity Service
用户、资料、业务身份、权限。

Content Service
视频、稿件、投稿、发布与互动。

Knowledge Service
非遗知识条目、来源、审核与版本。

Learning Service
学习路径、知识卡片、测验、进度和成就。

Commerce Service
店铺、商品、库存、订单、退款与售后。

Notification Service
站内通知与业务事件提醒。

Task Service
用户待办、审核任务、异步任务状态。

Moderation Service
内容、商品、来源和举报审核。

Audit Service
重要操作与安全审计。

这些是逻辑模块，不要求分别部署。

优先复用现有用户、工作区与异步任务系统。

## 6. 跨板块非遗知识对象

建立统一 HeritageTopic / HeritageItem 领域模型。

至少包含：

- topic_id
- title
- category
- region
- description
- source_refs
- verification_status
- reviewer
- version
- updated_at

支持关联：

- 视频内容
- 创作作品
- 学习路线
- 知识卡片
- 文化人物
- 商品
- 文化活动

必须区分：

权威来源、用户投稿、商家宣传、模型生成内容、人工核验结果。

不得将未经验证的商家宣传自动写入可信非遗知识库。

## 7. 用户中心

构建四个核心视图：

### A. 身份总览

显示：

- 当前账户
- 已开通身份
- 可申请身份
- 当前身份工作台
- 身份审核状态
- 快速切换
- 最近任务

### B. 个人文化档案

显示：

- 收藏
- 关注
- 学习进度
- 已参与文化主题
- 已获得成就
- 创作贡献
- 文化兴趣

文化兴趣画像涉及跨场景行为数据时，需要明确说明用途并获得适当授权，支持关闭和撤回。

不得默认将购物行为直接用于敏感画像或无关推荐。

### C. 身份工作台

根据当前业务身份展示对应工作空间。

创作者：
作品、草稿、投稿、审核、素材、数据。

学习者：
学习路径、AI 老师、测验、知识卡片、学习记录。

买家：
订单、售后、收藏商品、地址。

卖家：
商品、库存、订单、营销、售后、经营数据。

知识贡献者：
资料提交、来源证据、纠错、审核状态。

审核员：
待审任务、审核决策、来源核对。

管理员：
授权、用户管理、平台风险、审计。

### D. 消息与任务中心

支持：

- 系统通知
- 投稿结果
- 身份申请结果
- 商品审核
- 订单状态
- 售后进度
- 学习提醒
- 未完成任务

通知必须和真实业务事件关联。

不得使用静态通知模拟正式功能。

## 8. 视频社区业务闭环

至少实现或验证：

Creator Activation
→ Content Draft
→ Media Upload
→ Submit
→ Moderation
→ Publish
→ Playback
→ Interaction
→ Creator Dashboard

保留与现有 AI 图文脚本工作台的衔接。

脚本版本可以作为内容创作来源，但不得直接覆盖原有 ScriptVersion 数据结构。

需要明确：

- 上传限制
- 文件存储
- 内容审核
- 版权声明
- 发布状态
- 收藏、点赞和评论的数据一致性
- 举报与申诉
- 内容删除和恢复策略

至少有一个真实可播放视频完成从投稿到发布的全过程。

## 9. AI 文化学习闭环

建立：

Video / Heritage Topic
→ Knowledge Retrieval
→ AI Explanation
→ Evidence Display
→ Knowledge Card
→ Quiz
→ Progress Save
→ Achievement

模型路由采用项目已有能力。

优先将权威非遗资料作为教学事实来源。

使用 RAG 或等效检索时必须保留来源标识和版本。

没有可靠来源时：

- 明确说明无法确认。
- 不得伪造历史事实。
- 不得自动判定学习资料已核实。

成长成就基于实际完成和验证事件发放。

成就规则应具备版本、去重和撤销/纠错机制，避免重复发放。

AI 学习聊天记录、正式知识卡片与经核验的学习成果应分别保存。

## 10. 电商业务闭环

建立：

Merchant Application
→ Merchant Review
→ Store Setup
→ Product Draft
→ Product Moderation
→ Listing
→ Cart
→ Checkout
→ Order
→ Payment State
→ Fulfillment
→ After-sales

首期可以先实现交易沙盒。

正式支付上线之前，必须确认：

- 目标经营地区
- 商业主体
- 支付服务商准入
- 退款流程
- 资金结算责任
- 隐私与消费者保护
- 商品类别与经营资质

不允许自建存储银行卡敏感信息。

真实支付状态必须由可信支付服务端结果更新。

必须验证：

- 库存扣减并发安全
- 订单幂等
- 支付回调真实性与去重
- 取消与退款状态
- 用户订单数据隔离
- 商家经营权限
- 商品审核与下架

在未接入合规支付渠道前，必须明确标记为 SANDBOX，不得宣称支持正式交易。

## 11. 前端信息架构与 AI 交互

顶部四大入口：

视频社区 / 非遗电商 / AI 学习 / 用户中心。

账户菜单显示当前业务身份。

身份切换后：

- 切换工作台首页。
- 切换导航与任务入口。
- 恢复对应工作区的项目和最近任务。
- 保持统一登录会话。
- 不丢失未完成且已保存的任务。
- 不改变其他身份的授权。

AI 助手根据工作上下文提供不同能力：

创作者 → 创作助手。

学习者 → 非遗老师。

卖家 → 经营助手。

知识贡献者 → 来源整理助手。

AI 助手共用模型网关，但使用独立的工具权限、上下文构建器、输入输出契约和评估标准。

禁止用户通过 Prompt 直接调用未授权管理工具。

UI 流程：

Information Architecture
→ Wireframe
→ Interaction States
→ Design Tokens
→ Responsive Design
→ 用户确认
→ 正式实现。

在结构设计确认之前，不大规模重做现有 UI。

## 12. 数据库与迁移

根据真实现有 Schema 设计新增表及关系。

优先考虑：

role_grants
role_applications
creator_profiles
merchant_profiles
learning_profiles
heritage_topics
knowledge_sources
learning_progress
quiz_attempts
achievement_grants
content_items
content_moderation_cases
shops
products
product_variants
inventory_movements
orders
order_items
payment_events
notifications
user_tasks
audit_events

根据项目实际已有表进行复用和映射。

必须具备：

- 外键与唯一约束
- Scope / Ownership
- Index
- Transaction Boundary
- State Machine
- Migration
- Backup
- Compatibility
- Rollback or Forward Recovery

不可因新增身份模型而破坏现有 users / workspaces / memberships。

## 13. 可靠事件与后台任务

使用已有 Redis / Dramatiq 系统（如当前仍可用）。

涉及数据库事务后触发通知、学习奖励、审核任务等跨模块事件时，评估 Transactional Outbox 或等效可靠事件发布机制。

核心目标：

业务状态成功提交后，即使 Worker 临时故障，相关事件最终仍能可靠处理。

每个消费者必须处理重复消息。

需要验证：

- 任务幂等
- 失败重试
- 取消
- 页面刷新
- Worker 重启
- 跨身份恢复
- 重复事件不会重复发放成就或重复修改订单

## 14. API 契约

实际制定 OpenAPI 契约。

至少覆盖：

- 用户资料
- 当前授权身份
- 身份申请
- 身份开通与撤销
- 工作台总览
- 通知和任务
- 创作者作品
- 投稿审核
- 非遗知识
- 学习路径
- 学习进度
- 成就
- 商家入驻
- 商品
- 订单

后端权限不得依据前端提交的 role 名称直接放行。

必须从持久化授权与实际资源归属计算有效权限。

前端的角色切换值只是当前工作上下文。

## 15. 功能测试与验收

建立可自动化的功能矩阵。

每项功能必须覆盖：

UI Entry
→ API
→ Domain
→ Database
→ Business Result
→ Test Evidence

至少测试以下场景：

1. 一个账户开通创作者和学习者两种身份。
2. 在两种身份之间切换且保留各自工作记录。
3. 退出并重新登录后身份状态仍然正确。
4. 未授权用户不能直接访问创作者私有接口。
5. 用户自行构造管理员身份请求被拒绝。
6. 创作者上传真实视频并完成审核发布。
7. 学习者完成一次真实 AI 学习和测验。
8. 完成测验后成长记录只增加一次。
9. 知识贡献者提交无来源资料，不会自动成为可信知识。
10. 商家申请被拒绝后无法管理商品。
11. 商家管理自己的商品，但不能访问其他店铺订单。
12. 买家完成一次沙盒下单。
13. 两个并发订单不会错误超卖。
14. 通知重复投递不会生成重复业务结果。
15. 页面刷新和 Worker 重启不丢失已完成状态。
16. 审核员不得审核自己的投稿。
17. 已有 HAHA 图文脚本生成和历史资料不受影响。

执行：

Python Unit / Integration Tests

API Contract Tests

PostgreSQL Integration Tests

Frontend Component Tests

Browser E2E

Security Tests

Concurrency / Recovery Tests

AI Eval

Regression Tests

不得以 Mock 单独替代真实功能验收。

## 16. 遗留安全缺陷

检查前期 HAHA 升级报告所列四项安全阻断：

- 开发认证 fail-open 风险
- DOCX 上下文 Prompt 注入
- XML 解析实体膨胀
- DOCX ZIP 解压放大

如果尚未修复，纳入发布阻断清单。

同时补充：

- 身份权限提升
- 跨账户和跨店铺数据访问
- 隐私资料泄露
- 视频上传安全
- 支付回调伪造
- AI Prompt Injection
- 内容与商品审核绕过
- 个人信息保留、导出和删除

未经验证，不得宣布 Production Ready。

## 17. 分阶段实施及继续执行

按依赖顺序执行。

### Gate A：架构与数据底座

完成项目扫描、目标架构、身份授权、业务对象、API 和迁移。

### Gate B：身份中心最小真实闭环

实现同账户多身份、申请、授权、切换、工作台总览、任务持久化及权限测试。

### Gate C：视频与 AI 学习闭环

打通创作投稿、审核发布、知识关联、AI 教学、学习记录与成长事件。

### Gate D：买卖家交易闭环

实现卖家申请、商品、审核、库存、订单和安全的交易沙盒。

### Gate E：四大板块 UI 集成

先提交完整 UI/UX 预览，等待用户确认。

确认后实现页面与真实后端连接。

### Gate F：生产工程

完成：

- 功能完整性验证
- 安全审计
- AI Eval
- 并发与恢复
- 备份恢复
- 监控告警
- 性能和容量测试
- CI/CD
- 部署与回滚验证

每个 Gate 提供真实执行证据。

当上一 Gate 通过时，可继续处理不依赖用户审批的后续工程任务。

涉及 UI 重大变更、实际资金、不可逆数据操作和正式上线时必须先取得授权。

## 18. 交付标准

交付：

ARCHITECTURE_AUDIT.md

PRODUCT_DOMAIN_MODEL.md

IDENTITY_AUTHORIZATION_SPEC.md

API_CONTRACTS.md

DATABASE_MIGRATION_REPORT.md

FRONTEND_UX_SPEC.md

AI_LEARNING_EVAL.md

COMMERCE_SANDBOX_REPORT.md

FUNCTIONAL_VALIDATION_REPORT.md

SECURITY_TEST_REPORT.md

PRODUCTION_READINESS_REPORT.md

FINAL_DELIVERY.md

报告必须提供实际代码路径、测试命令、测试结果、数据库迁移记录和运行证据。

没有通过的功能标记：

PARTIAL / FAIL / UNKNOWN / BLOCKED。

严禁伪造已完成的工作台、订单、AI 成果或测试证据。

## 19. 最终完成标准

最终用户能够：

1. 用同一账户登录 HAHA。
2. 查看、开通或申请多种身份。
3. 在不同身份的真实工作台中切换。
4. 完成创作投稿与审核发布。
5. 观看视频并进入关联的 AI 非遗学习。
6. 保存知识卡片、测验结果和成长档案。
7. 使用买家与卖家功能完成经过验证的沙盒交易流程。
8. 统一查看通知、任务与身份状态。
9. 刷新、重启、切换身份后不丢失正式数据。
10. 所有业务均经过真实权限检查与功能验收。

注意：沙盒交易验证不代表正式支付上线完成；公网发布必须另行满足生产和合规门禁。

**现在从当前项目代码扫描开始执行，保留既有 HAHA 架构，按照工程证据逐步实现目标闭环。**
