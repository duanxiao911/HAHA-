# HAHA 飞颐

HAHA 飞颐是一个面向非遗内容创作与传播的本地 MVP。目前项目包含内容社区、AI 对话式创作工作台、模型路由、知识检索与 Run 调用证据面板。

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
- Streamlit 1.40+
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
python -m pip install -e . pytest ruff
```

### 3. 配置模型（可选）

环境变量名称参见 [`config/model.env.example`](config/model.env.example)。不要把真实 API Key 写进仓库。

当前 PowerShell 会话可这样设置：

```powershell
$env:DEEPSEEK_API_KEY = "你的密钥"
$env:DEEPSEEK_MODEL = "deepseek-chat"
```

如果不配置密钥，仍可使用“本地演示”模式检查页面与完整交互流程。

### 4. 启动网页

```powershell
python -m streamlit run app.py --server.port 8530
```

浏览器访问：<http://localhost:8530>

AI 工作台入口：<http://localhost:8530/?space=script>

## 验证

```powershell
python -m pytest
python -m ruff check .
```

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
└─ tests/                         # 自动化测试
```

## 安全说明

- API Key 仅从环境变量读取。
- `.env`、`model-config.ps1`、缓存和本地产物均被 Git 忽略。
- 提交前应确认 `git status` 中没有密钥文件或本地系统目录。

## 开发状态

当前重点是完成“模型选择 → 会话状态 → 模型路由 → 实际调用 → Run 证据”的可靠闭环。后续计划包括会话持久化、草稿保存、真实知识库检索增强及完整投稿流程。
