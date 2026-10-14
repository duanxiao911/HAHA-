# HAHA 项目开发规则

本仓库的所有开发、升级、修复、重构、测试和发布工作，默认遵守
[`docs/governance/AI_FULLSTACK_SOP_V1.md`](docs/governance/AI_FULLSTACK_SOP_V1.md)。
开始任务前必须完整读取该文件，并按任务风险选择轻量路径或完整路径；不得跳过适用门禁而不说明原因。

## 项目级补充约束

- 修改前先检查 Git 状态、现有规范、真实代码、运行环境与测试证据，保留用户已有改动。
- 继续使用 Next.js、FastAPI、PostgreSQL、Redis、Dramatiq 和 JWT 的现有架构；未经架构决策不得引入平行技术栈。
- 跨模块能力实行 Contract First，并明确领域状态、权限、错误、幂等、审计和迁移边界。
- UI 重大结构变化须先完成信息架构、状态与预览，并取得用户确认；普通修复和已确认的小改动可直接实施。
- 本地演示、Mock、静态数据、按钮可点击或 API 200 均不能单独作为功能完成证据。
- 按风险执行单元、契约、集成、真实浏览器、回归、安全与真实环境测试，并保存可复核证据。
- 认证和授权必须 fail-closed；开发认证只能显式开启，生产或预发布环境不得静默回退。
- 不得提交密钥、个人数据、内部 Prompt、专有知识库或其他不应公开的资产。
- 未经用户明确授权，不执行公开发布、真实付费、不可逆数据操作或可能暴露核心知识产权的交付。
- 严格区分 Prototype、Engineering Complete、Functionally Validated、Production Candidate 和 Production Ready。
- 未通过独立 Production Readiness Gate，不得宣布 Production Candidate 或 Production Ready。

若 SOP 引用的上游权威资料在当前任务中不可访问，明确记录 `SOURCE_MISSING`，继续执行能够确定的部分，
不得声称已复核未读取的资料。若项目规则与用户当前明确要求冲突，以用户当前要求为准，但仍须遵守安全和证据真实性边界。
