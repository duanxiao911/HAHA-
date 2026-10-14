# AI 全栈应用开发统一 SOP V1.0

**状态：默认工程规范**

**适用范围：** 网站、App、小程序、Python 工具、AI 工作台、Agent 系统、自动化系统、媒体软件、现有项目升级及新产品开发。

**核心依据：**

- 软件工程 × Python × Production Engineering 知识树 V1.0
- Project Architecture Scanner V2.0
- Production Readiness Gate V1.0
- AI × 数学 × 自然科学知识树
- Agent 架构：六职责域、三横切系统
- Product Function Integrity Gate
- UI/UX 设计启动规范

这些文件是既有知识体系的权威来源。执行前应优先读取能够访问到的原文。若未取得原文，记录 SOURCE_MISSING，以本文规则执行可确定的部分，不得假装已经逐项复核原文。

## 0. 总原则

必须坚持：

**Concept ≠ Architecture ≠ Implementation ≠ Runtime ≠ Validation**

**业务问题 → 技术原理 → 架构决策 → 工程实现 → 真实验证 → 交付结果。**

基本约束：

1. Business First：先识别业务需求，不先决定技术栈。
2. Minimum Sufficient Architecture：选择满足需求的最低复杂度方案。
3. Reuse Before Rebuild：先复用可靠模块，不盲目重构。
4. Contract First：跨模块功能先定义契约和状态边界。
5. Evidence Based：没有测试与运行证据，不宣称功能完成。
6. Security by Design：安全不能仅留到上线之前。
7. Cost Aware：控制模型、基础设施、存储与维护成本。
8. Reversible Changes：高风险变更优先提供恢复与回滚路径。
9. User Approval：涉及 UI 重大改版、不可逆操作、真实付费、公开发布时保留用户决策权。
10. Controlled Knowledge Update：新知识经解释与验证、得到用户确认后再正式收录。

本 SOP 是开发过程控制框架，不要求所有小任务都执行全量工程流程。

简单修复采用轻量路径；完整产品或架构升级采用完整路径。省略某项门禁必须说明不适用原因。

---

# G0｜需求发现与语义对齐

接收用户的自然语言、截图、草图或功能想法后：

- 先识别用户真正想解决的问题。
- 将白话转化为正确的软件工程术语。
- 明确目标用户和使用场景。
- 区分用户目标、方案假设和技术实现。
- 主动指出隐藏需求。
- 发现不合理设计时提供证据和替代方案。

至少明确：

- User Goal：用户目标
- Use Case：使用场景
- User Journey：用户路径
- Functional Requirements：功能需求
- Non-functional Requirements：非功能需求
- Data Requirements：数据需求
- Risk & Constraints：风险与约束
- Acceptance Criteria：验收条件

主动检查用户可能遗漏的：

空状态、异常输入、撤销、保存、恢复、重复操作、跨页面切换、弱网、断网、权限、成本、兼容性、数据删除、备份、导出、可维护性。

产出需求与验收映射。

不得把用户提出的初步方案直接当作最终技术规格。

---

# G1｜Project Architecture Scanner

修改现有项目之前必须扫描真实代码和运行环境。

检查：

- Git 工作区和当前提交
- README 与已有规范
- 项目目录和入口
- 前端页面与组件
- Python / 其他后端框架
- API 与数据库
- AI 模型和 Tool/Skill
- Workflow、Worker、Runtime
- 数据状态与持久化
- 配置与密钥管理
- 环境和依赖版本
- 测试、CI/CD
- 部署方式
- 现有故障及技术债
- 硬件与预算约束

对模块标记：

KEEP / ADAPT / REPLACE / REMOVE / UNKNOWN。

输出架构扫描、真实能力清单和差距分析。

保护已有代码、数据、资产及用户未提交修改。

未扫描的模块不得推断为不存在。

---

# G2｜Architecture Decision（架构决策）

按照实际业务选择架构。

必须分别考虑：

## 前端架构

Presentation（展示）

Interaction（交互）

UI State（界面状态）

Server State（服务端数据状态）

API Client（接口客户端）

Media / AI Interaction（媒体与 AI 交互，按需）

Design System（设计系统）

不得默认前端必须使用特定框架。

## 后端架构

API / Controller

Application Service

Domain Logic

Repository / Persistence

Infrastructure Adapter

Background Worker（需要时）

External Integration

优先模块化单体，只有独立部署和扩展需求得到验证时才考虑微服务。

## Python 工程

Python 包与模块边界、环境和依赖管理、类型系统、配置、异常、日志、测试、异步处理、数据库迁移和可执行入口均须明确。

技术可考虑 FastAPI、Pydantic、SQLAlchemy、Alembic、Pytest、Ruff，但必须根据已有项目情况评估。

Python 不替代产品架构、业务建模或前端工程。

## AI 工程

采用六职责域：

- Business & Decision
- Intelligence & Reasoning
- Context & Knowledge
- Orchestration & Control
- Action & Integration
- Runtime & Reliability

三个横切领域：

- Security / Governance
- Observability / Evidence
- Evaluation / Controlled Improvement

Workflow 与 Agent 必须按真实任务选择。

步骤稳定的任务优先确定性 Workflow。

需要开放式规划和动态决策时才使用 Agent。

未经测试不得宣称 Multi-Agent、Self-Evolving 或 RSI 已实现。

## 系统级选择

评估：

- 数据库与缓存
- 身份与权限
- 文件与对象存储
- 同步/异步
- 并发与队列
- 部署与成本
- 运行环境
- 数据一致性
- 性能、容量和扩展性

重要决策必须记录 ADR（Architecture Decision Record，架构决策记录），包含方案、依据、替代方案、代价和验证条件。

---

# G3｜Domain / State / Contract Engineering

编码前建立可检查的数据与接口契约。

## 领域对象

明确：

Entity、Value Object、Relationship、Aggregate、Invariant、Lifecycle。

区分业务数据、运行状态和临时缓存。

## 七类状态

根据适用情况分别管理：

1. Context State（上下文状态）
2. Session State（会话状态）
3. Workflow / Run State（执行状态）
4. Workspace / Artifact State（工作区与产物状态）
5. Long-term Memory（长期记忆）
6. Business State（业务权威状态）
7. Evidence / Audit State（证据与审计状态）

不得把全部状态混入页面组件或单个 JSON 文件而不评估一致性风险。

## 接口与契约

定义：

- API Schema / OpenAPI
- 输入与输出
- 错误码
- 版本
- 认证与授权
- 幂等性
- 超时
- 重试策略
- 状态转换
- 资源所有权
- 并发冲突行为

前端 TypeScript 类型在条件允许时由 API 契约生成。

数据库变更必须考虑迁移、兼容和回滚策略。

---

# G4｜UI/UX Design Gate

遵守：

需求语义对齐
→ 专业术语转换
→ 信息架构
→ 布局线框图
→ 交互与状态
→ 设计预览
→ 用户确认
→ 正式实现。

必须考虑：

- Information Architecture
- User Journey
- Design Tokens
- Typography
- Spacing
- Alignment
- Component States
- Responsive Layout
- Accessibility
- Keyboard Interaction
- Error / Empty / Loading States
- Visual Hierarchy
- Workspace Density

工作台需要优先检查主画布、侧栏和有效空间利用率。

不能靠堆叠卡片代替专业 UI 设计。

用户已确认的 UI 规范应作为实现约束，不在未经许可时擅自改变核心交互。

普通 Bug 修复和已确认的小型样式调整无需重复进行完整 UI 审批。

---

# G5｜Engineering Implementation

以 Vertical Slice（垂直功能切片）推进开发。

每个切片必须完成：

Frontend Entry
→ API
→ Application Service
→ Domain Logic
→ Storage / Tool / AI
→ Validated Result
→ UI Feedback。

实现要求：

- 模块职责清晰。
- 输入校验。
- 错误处理。
- 真实数据流。
- 权限检查。
- 版本控制。
- 结构化日志。
- 合理的事务边界。
- 必要的自动化测试。
- 代码风格与类型检查。

不得用假按钮、静态假数据或仅 UI 展示冒充功能完成。

不要同时无故重构无关模块。

高风险变更采用小批次、可回滚提交。

---

# G6｜AI Engineering Gate（适用 AI 项目）

AI 功能必须经过独立设计，不等于接入一个模型 API。

检查：

- Model Capability
- Model Routing
- Context Engineering
- RAG / Knowledge Retrieval
- Tool / Skill Contract
- Workflow / Orchestration
- Prompt Injection Boundary
- Output Schema Validation
- Evidence / Grounding
- Eval Dataset
- Cost / Latency
- Fallback / Human Review

模型输出应区分：

Observation（观察）

Inference（推断）

Hypothesis（假设）

Verified Fact（经验证事实）

模型建议不能直接变成有风险的外部动作。

关键操作需要 Schema 校验、领域约束检查、权限检查和可追踪执行记录。

不允许把“模型输出了 JSON”作为工具能力成功的证明。

---

# G7｜Product Function Integrity Gate

对全部核心功能建立需求追踪链：

Requirement
→ Feature
→ UI Entry
→ API
→ Service
→ State
→ Output
→ Test
→ Evidence。

每个功能必须记录：

- Feature ID
- Expected Behavior
- Actual Behavior
- Code Location
- API / Service
- State / Data
- Test Case
- Runtime Evidence
- Status

状态只能是：

PASS / PARTIAL / FAIL / UNKNOWN / N/A。

按钮能点击不代表成功。

API 返回 200 不代表业务完成。

数据库有记录不代表用户能正常使用。

只有完整用户任务得到真实验证后才能标记对应功能 PASS。

---

# G8｜Software Testing & AI Evaluation

按风险制定测试覆盖范围。

至少考虑：

- Unit Test
- Integration Test
- API Contract Test
- Browser E2E
- Regression Test
- Data Integrity Test
- Concurrency Test
- Recovery Test
- Security Test
- Performance / Load Test
- Compatibility Test
- AI Eval（适用时）

需要真实媒体、文件、图像、视频、硬件或模型服务的能力，必须补充真实环境测试。

Mock 只能证明受模拟条件覆盖的逻辑。

AI Eval 应包含正常案例、边界案例、失败案例、恶意输入及人工审核样本。

建立固定的基准样本和指标，并记录模型版本、成本和误差。

不得把少量样本全通过扩大解释为真实世界整体质量可靠。

---

# G9｜Security & Reliability Gate

依据系统风险检查：

## Security

认证、授权、输入校验、敏感信息保护、文件上传、数据隔离、依赖风险、API 密钥、提示注入、权限提升、供应链、第三方许可证。

## Reliability

事务、幂等、超时、取消、重试、并发、租约、检查点、任务恢复、备份恢复、补偿与对账。

## Observability

日志、请求 ID、任务 ID、指标、追踪、告警、故障诊断和运行证据。

## Performance

CPU/GPU、内存、延迟、吞吐、带宽、存储、费用与资源配额。

## Operations

配置分离、CI/CD、环境隔离、数据库迁移、部署、冒烟测试、发布责任人和回滚演练。

上线必须满足所确定风险等级对应的阻断门禁。

不能因为是个人开发者，就默认忽视数据保护和安全基础。

---

# G10｜Release & Production Readiness

发布前独立评估：

- 功能完整性
- 数据安全
- 权限
- 可靠性
- 恢复能力
- 真实环境测试
- 负载与成本
- 监控告警
- CI/CD
- 依赖和许可证
- 发布回滚
- 运维责任

明确区分：

Prototype

Engineering Complete

Functionally Validated

Production Candidate

Production Ready

这些不是仅凭开发阶段名称自动授予的状态。

部署成功也不代表 Production Ready。

存在适用的重大阻断项时，不得宣称正式生产就绪。

---

# G11｜Delivery & Knowledge Evolution

每次开发结束，根据任务规模输出：

- 实际修改摘要
- 架构决策
- 文件路径
- API / Schema 变化
- 测试执行结果
- 运行证据
- 未完成事项
- 已知风险
- 运行与恢复方法
- 后续维护建议

复杂项目应保留：

ARCHITECTURE_AUDIT.md

ARCHITECTURE_DECISIONS.md

IMPLEMENTATION_PLAN.md

API_CONTRACTS.md

TEST_REPORT.md

FUNCTIONAL_VALIDATION_REPORT.md

PRODUCTION_READINESS_REPORT.md

以上为建议文件名，不要求小型任务机械创建所有文件。

开发过程中发现的新原理或通用工程模式，应先在对话中解释、验证，再提交用户确认，之后才能更新底层知识库。

项目特有规则不能未经审核上升为全局工程定律。

---

# 永久横切规则

## A. 模型与推理成本

新项目先做最低充分模型与推理强度评估。

简单问题用低成本配置。

复杂架构、跨仓库重构、深度故障分析和生产门禁可提高推理强度。

不得仅为追求高强度而浪费额度。

## B. 主动补漏

用户没有提出某项需求，不代表它不重要。

应主动发现：

数据丢失、功能缺口、权限漏洞、异常状态、依赖冲突、性能瓶颈、成本浪费、用户体验问题、维护困难及交付风险。

根据严重程度分级：

CRITICAL / HIGH / MEDIUM / LOW。

主动补充不等于擅自扩大产品范围。

## C. 知识产权与交付保护

对外分享前检查：

源码、完整工作流、Skill、Prompt、内部规则、知识库、模型路由、专有数据及商业机密。

默认保护内部架构。

可优先采用受控 API、服务接口或最小能力包对外交付。

未经明确授权，不公开仓库、不上传敏感资料、不披露内部实现。

## D. 用户决策边界

必须获得用户确认的事项：

- 重大 UI 结构变化。
- 不可逆数据修改。
- 高风险生产操作。
- 超出预算的付费调用。
- 商业产品公开发布。
- 可能暴露核心知识产权的交付。

一般可逆的开发和测试可按已授权任务自主执行。

## E. 结果真实性

严禁：

- 伪造测试通过。
- 伪造模型表现。
- 伪造部署结果。
- 伪造截图和运行日志。
- 以计划代替实现。
- 以 Mock 代替真实验收。
- 以配置文件存在代替运行能力存在。
- 用“代码已完成”宣称用户目标完成。

无法验证时标记 UNKNOWN 或 BLOCKED，并说明需要的条件。

## F. 跨项目适用原则

本 SOP 默认适用于所有开发任务。

项目级规则可进一步细化技术栈、UI、业务规范和测试要求，但不得绕过用户确认、安全边界及证据验收原则。

以上 SOP 自安装到相应环境起作为默认开发流程执行。
