# HAHA 飞颐

HAHA 飞颐正在从本地 Streamlit MVP 迁移为可上线的前后端分离产品。当前仓库同时包含旧界面和第一阶段生产后端核心；Streamlit 仅作为迁移期客户端，新的业务权威状态不再设计为依赖 `st.session_state`。

## 当前能力

- 非遗内容社区：首页频道、热门内容、地域探索与文化地图入口
- AI 创作工作台：以对话方式生成图文或视频内容方案
- 模型路由：支持本地演示、自动选择与 DeepSeek 文本模型
- Knowledge & Context：创作方法、运营策略、非遗事实三类知识检索
- Run 证据：展示 Provider、模型、调用模式、请求 ID、耗时、Token 与知识检索轨迹
- 内容发布：保留视频投稿与社区内容展示的基础流程

> 当前仍是本地开发阶段。未配置模型密钥时，“自动选择”会明确使用本地演示；直接选择 DeepSeek 会显示未配置错误，不会伪装成 API 成功。

## 技术栈

- Python 3.11+
- FastAPI + Pydantic（新 API 层）
- 框架无关的领域服务与 Run 状态机
- PostgreSQL/SQLAlchemy + Alembic；SQLite 仅作本地开发适配器
- Redis + Dramatiq 独立 Worker
- Next.js 16 正式 Web 前端（`web/`）
- Streamlit（迁移期旧界面）
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

推荐把 [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example) 复制为
`.streamlit/secrets.toml`，然后只在本机填写密钥。真实文件已被 Git 忽略，应用启动时会自动读取。

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

这是当前正式前端。`app.py` 的 Streamlit 页面仅保留作迁移期兼容入口，不再作为生产网页。

### 5. 启动 API

```powershell
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

`compose.yaml` 默认关闭认证以便本地联调；任何公网或共享环境都必须启用正式身份服务，不能沿用该设置。

## 验证

```powershell
python -m pytest
python -m ruff check .
python scripts/run_ai_eval.py
```

Phase B 的可观测性、CI、staging、真实浏览器 E2E 与 AI Eval 证据见
[`docs/evidence/phase-b-summary.md`](docs/evidence/phase-b-summary.md)。这些证据不等同于
Production Ready 宣告；托管 CI、staging 镜像构建和线上模型评测仍按发布门禁独立验收。

## 项目结构

```text
haha-platform-v2/
├─ app.py                         # Streamlit 页面与交互入口
├─ config/model.env.example       # 模型环境变量示例
├─ data/heritage_facts.json       # 非遗事实知识库
├─ scripts/import_heritage_facts.py
├─ src/haha_media/
│  ├─ feed.py                     # 社区演示数据
│  ├─ knowledge.py                # 三类知识检索与轨迹
│  ├─ model_router.py             # 文本/图像模型路由与调用证据
│  ├─ script_writer.py            # 创作生成链路
│  └─ theme.py                    # 页面视觉样式
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
