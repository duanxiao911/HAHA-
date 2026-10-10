# Streamlit 兼容层退役记录

日期：2026-10-10

## 结果

HAHA 的正式前端已统一为 `web/` 下的 Next.js 应用。Streamlit 兼容入口、主题、专用测试、浏览器检查脚本、示例配置和 Python 依赖已从 `main` 移除。

## 可恢复归档

- Git 分支：`archive/streamlit-legacy-2026-10-10`
- 归档提交：`7ffbfc9`
- 范围：旧 Streamlit 入口及截至退役前尚未提交的界面修改

本地未跟踪的 `.streamlit/secrets.toml` 未读取、未提交到 Git，已移动到仓库外的私有目录：

`E:\chatgtp\HAHA\streamlit-private-archive-2026-10-10\secrets.toml`

## 从 main 移除的内容

- `app.py`
- `src/haha_media/theme.py`
- `tests/test_app.py`
- `scripts/e2e_workspace_check.py`
- `scripts/e2e_parameter_check.py`
- `.streamlit/secrets.toml.example`
- `streamlit` 开发依赖和 `legacy-ui` 可选依赖组
- README 与生产架构文档中的活跃兼容入口说明

阶段报告中关于 Streamlit 到 Next.js 的历史描述继续保留，作为迁移证据，不属于运行时依赖。

## 验证要求

- 活跃代码、配置、测试和部署文件中不得再引用 Streamlit。
- 后端 pytest 与 Ruff 必须通过。
- Next.js lint 与生产构建必须通过。
- GitHub CI 与 Pages 发布必须在移除提交后重新通过。
