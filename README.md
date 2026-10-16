# HAHA 飞颐

HAHA 飞颐是采用 Next.js、FastAPI、PostgreSQL、Redis 与 Dramatiq 构建的非遗内容社区和 AI 创作平台。

项目开发、升级、验收与发布默认遵守
[`AI 全栈应用开发统一 SOP V1.0`](docs/governance/AI_FULLSTACK_SOP_V1.md)，并由根目录
[`AGENTS.md`](AGENTS.md) 补充 HAHA 项目级约束。

## 当前能力

- 非遗内容社区：首页频道、热门内容、地域探索与文化地图入口
- 社区发现闭环：内容详情、可信来源、搜索、收藏、想学、历史、关注、评论与消息
- 身份与文化成长中心：同账户多身份、服务端授权切换、身份申请、身份专属工作台、持久化任务与权限审计
- 学习成长中心：服务端学习档案、路径进度、来源化知识卡、服务端测验、每日任务、连续学习与幂等成就
- 非遗交易沙盒：卖家商品审核、版本化库存、买家购物车、单店结算、幂等订单、内部沙盒支付、履约与售后
- 内容关系网络：非遗项目、演示人物、地区、专题、活动与内容互相跳转
- AI 创作工作台：以对话方式生成图文或视频内容方案
- 模型路由：支持本地演示、自动选择与 DeepSeek 文本模型
- Knowledge & Context：创作方法、运营策略、非遗事实三类知识检索
- Run 证据：展示 Provider、模型、调用模式、请求 ID、耗时、Token 与知识检索轨迹
- 内容发布：六步本地投稿向导、AI 披露、事实来源检查、审核状态机与发布消息回流

> 当前仍是本地开发阶段。未配置模型密钥时，“自动选择”会明确使用本地演示；直接选择 DeepSeek 会显示未配置错误，不会伪装成 API 成功。

## 技术栈

- Python 3.11+
- FastAPI + Pydantic（新 API 层）
- 框架无关的领域服务与 Run 状态机
- PostgreSQL/SQLAlchemy + Alembic；SQLite 仅作本地开发适配器
- Redis + Dramatiq 独立 Worker
- Next.js 16 正式 Web 前端（`web/`）
- pytest
- Ruff

## 本地启动

### 1. 创建虚拟环境

```powershell
cd E:\chatgtp\HAHA\haha-platform-v2
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. 安装项目

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 3. 配置模型（可选）

环境变量名称参见 [`config/model.env.example`](config/model.env.example)。不要把真实 API Key 写进仓库。

当前 PowerShell 会话可这样设置：

```powershell
$env:DEEPSEEK_API_KEY = "你的密钥"
$env:DEEPSEEK_MODEL = "deepseek-chat"
```

如果不配置密钥，仍可使用“本地演示”模式检查页面与完整交互流程。

### 4. 启动正式网页（推荐）

```powershell
cd web
pnpm install
pnpm build
pnpm start
```

浏览器访问：<http://localhost:3000>

这是当前唯一正式 Web 前端。

### 5. 启动 API

```powershell
$env:HAHA_ENVIRONMENT = "development"
$env:HAHA_AUTH_MODE = "dev"
$env:HAHA_ALLOW_DEV_AUTH = "true"
python -m uvicorn haha_api.main:app --app-dir src --port 8000 --reload
```

健康检查：<http://localhost:8000/health>

接口文档：<http://localhost:8000/docs>

API 环境变量参见 [`config/api.env.example`](config/api.env.example)。容器入口参见
[`Dockerfile.api`](Dockerfile.api)。

前端和 API 需要同时运行。若修改了前端代码，请重新执行 `pnpm build` 后再执行 `pnpm start`。

### 6. 启动完整前后端开发栈

具备 Docker 的环境中，以下命令会同时启动 PostgreSQL、Redis、数据库迁移、API、Worker 和 Next.js：

```powershell
docker compose up --build
```

- Next.js：<http://localhost:3000>
- FastAPI：<http://localhost:8000/docs>
- PostgreSQL 和 Redis 只在容器网络中开放。

`compose.yaml` 通过三项显式变量开启仅限本机的开发认证，并把 Web/API 端口绑定到
`127.0.0.1`。源码默认值为 production + JWT；漏配认证变量或密钥时 API 会拒绝启动。
任何公网或共享环境都不得设置 `HAHA_ALLOW_DEV_AUTH=true`。

## 验证

```powershell
python -m pytest
python -m ruff check .
python scripts/run_ai_eval.py
```

Phase B 的可观测性、CI、staging、真实浏览器 E2E 与 AI Eval 证据见
[`docs/evidence/phase-b-summary.md`](docs/evidence/phase-b-summary.md)。托管 CI、staging 镜像构建和
小预算线上模型评测均已通过；这些证据仍不等同于 Production Candidate 或 Production Ready
宣告，正式发布资格需通过后续独立门禁。

Phase C 已补齐运行 SSE、取消、失败任务运维界面，以及基于不可变镜像的外部 staging 发布与
回滚包。发布操作从 [`docs/operations/release-runbook.md`](docs/operations/release-runbook.md)
开始。P0 安全阻断项已经修复并有回归证据；独立 Production Readiness Gate 尚未执行，
因此当前状态仍不是 Production Candidate。

Phase D 已在不新增普通后端技术栈的前提下，完成社区侧的本地可交互闭环：统一数据契约、
内容详情、搜索、文化档案、消息、项目/人物/地区关联、投稿与本地审核发布，并在 Docker 环境
执行 390/768/1024/1280/1440 五档真实浏览器验收。评论、知识注释和审核结果仍明确标记为
本地演示，尚未接入真实媒体存储、审核后台或内容 API。详见
[`docs/reports/phase-d-community-loop-2026-10-12.md`](docs/reports/phase-d-community-loop-2026-10-12.md)。

User Center Gate C1 已收口多身份上下文、账户资料、隐私偏好、收藏、想学、稍后看、关注、
观看历史、文化足迹聚合和站内消息。身份切换已移到顶部账户菜单，专业工作台只对相应身份显示；
学习路径、测验和成就由独立 Gate C3 在同一账户体系中实现，不在 C1 验收证据中回填。FastAPI + PostgreSQL 主链已完成
390/768/1440 三档真实浏览器验收，并覆盖首次并发建号。开发环境仍为显式 opt-in 的本机身份，
不等于正式上线；收口证据见 `docs/reports/2026-10-15_user-center-gate-c1-closeout/`。

Account Session G2 已提供仅限内部测试的真实账户闭环：PBKDF2 密码摘要、短期 JWT、服务端
刷新会话、原子单次轮换、退出撤销、失败锁定、认证审计和 `/login` 真实表单。账户不开放公众
注册，授权仍以 PostgreSQL membership 为准。创建或轮换内部账户时只通过环境变量传入密码：

```powershell
$env:HAHA_BOOTSTRAP_PASSWORD = "至少 12 位的本地测试密码"
docker compose exec -T -e HAHA_BOOTSTRAP_PASSWORD=$env:HAHA_BOOTSTRAP_PASSWORD api `
  python scripts/bootstrap_internal_account.py `
  --user-id internal-user --workspace-id internal-workspace `
  --email internal@example.local --role owner
```

设计与运行证据见
[`docs/reports/2026-10-14_account-session-g2/FUNCTION_ACCEPTANCE_REPORT.md`](docs/reports/2026-10-14_account-session-g2/FUNCTION_ACCEPTANCE_REPORT.md)。

Browser Session G3 已将 G2 的浏览器令牌从 `sessionStorage` 迁移到 Next.js 同源 BFF 管理的
HttpOnly/SameSite Cookie；所有变更请求校验同源 Origin 与 CSRF Token，刷新令牌只在服务端
轮换。后端 access token 绑定数据库会话 ID，用户可在用户中心查看并撤销单个或全部会话，撤销
后未过期 access token 也会立即失效。GitHub Pages 仍是明确隔离的无认证静态演示，不承载真实
会话。设计见 [`docs/architecture/browser-session-gate-g3.md`](docs/architecture/browser-session-gate-g3.md)，
真实环境证据见 `docs/reports/2026-10-14_browser-session-g3/`。G3 仍只面向内部测试与受控展示，
没有执行独立 Production Readiness Gate，也不代表 Production Candidate。

Multi-role Workbench G4 在 G3 安全会话之上增加服务端权威的当前身份投影。浏览者、学习者和
买家在“今日”看到真实文化资产、观看记录、身份任务与明确能力边界；创作者等专业身份才显示
对应工作台入口，避免把尚属 Gate C3/D 的能力伪装成已完成工作台。
客户端不能通过角色参数伪造管理员工作台。尚未接入的 AI 老师、知识稿件、真实支付与统一审核
能力会明确显示为 `blocked`，不生成虚构收入或权威知识结论。架构契约见
[`docs/architecture/multi-role-workbench-g4.md`](docs/architecture/multi-role-workbench-g4.md)，真实环境验收与
剩余风险见 `docs/reports/2026-10-14_multi-role-workbench-g4/`。G4 不代表 Production Candidate。

Learning Center Gate C3 已复用 learner grant 与统一账户，补齐路径、课程节点、版本化进度、
来源化知识卡、服务端判分的不可变答题记录、事件驱动每日任务、连续学习和幂等可审计成就，并同步
到用户中心成长汇总。当前课程只用于内部机制验证并标记 `demo_only`；没有真实模型与可信知识检索
接口时，“AI 非遗老师”明确保持 `BLOCKED`。架构契约与本地验收边界见
[`docs/architecture/learning-center-gate-c3.md`](docs/architecture/learning-center-gate-c3.md)。C3 是中间
Gate，未执行公开发布或独立 Production Readiness Gate。

Commerce Gate D 已复用 `buyer`、`seller`、`reviewer` 与统一账户，补齐店铺、商品独立审核、
版本化库存、购物车、单店事务结算、幂等订单、明确标记的内部沙盒支付、履约与售后。系统不采集
支付凭证，不处理真实资金；商品来源仍标记为卖家自述且非权威认证。架构、迁移和验收边界见
[`docs/architecture/commerce-gate-d.md`](docs/architecture/commerce-gate-d.md)。真实支付、退款、分账、
物流和商业合规仍为 `BLOCKED`，Gate D 不代表 Production Candidate。

Gate A–D 的统一收口口径见
[`docs/architecture/gates-a-d-closure.md`](docs/architecture/gates-a-d-closure.md)：已冻结的内部范围已经闭环，
但正式媒体链路与真实 AI 非遗老师仍分别为 `OPEN` / `BLOCKED`，不能把前四 Gate 无条件表述为 100%。

## 项目结构

```text
haha-platform-v2/
├─ config/model.env.example       # 模型环境变量示例
├─ data/heritage_facts.json       # 非遗事实知识库
├─ scripts/import_heritage_facts.py
├─ src/haha_media/
│  ├─ knowledge.py                # 三类知识检索与轨迹
│  ├─ model_router.py             # 文本/图像模型路由与调用证据
│  └─ script_writer.py            # 创作生成链路
├─ src/haha_core/
│  ├─ domain.py                   # 项目、参数版本、Run 与脚本版本
│  ├─ repository.py               # 持久化接口与开发适配器
│  ├─ service.py                  # 生成应用服务和生命周期编排
│  └─ verifier.py                 # 独立结果验证
├─ src/haha_api/
│  └─ main.py                     # 新 FastAPI 入口
├─ src/haha_worker/                # Redis/Dramatiq 后台任务
├─ migrations/                     # Alembic 数据库迁移
├─ web/                            # Next.js 正式前端
├─ compose.yaml                    # 完整本地服务栈
└─ tests/                         # 自动化测试
```

## 安全说明

- API Key 仅从环境变量读取。
- `.env`、`model-config.ps1`、缓存和本地产物均被 Git 忽略。
- 提交前应确认 `git status` 中没有密钥文件或本地系统目录。

## 开发状态

第一阶段已建立 `Project → BriefVersion → Run → Verification → ScriptVersion` 链路。完整生产迁移边界和后续阶段见 [`docs/production-architecture.md`](docs/production-architecture.md)。
