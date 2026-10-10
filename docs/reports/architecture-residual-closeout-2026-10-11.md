# Python 架构残余清理与联调收口报告

日期：2026-10-11

## 收口结果

- 删除仅由旧测试引用的 `haha_media.feed` 与 `haha_media.project_store` 原型模块。
- 删除对应的 `test_feed.py` 与 `test_project_store.py`。
- 本地虚拟环境已卸载 Streamlit；仓库依赖、运行代码和 Git 跟踪文件均不再包含 Streamlit。
- Web 容器要求显式提供 `NEXT_PUBLIC_API_BASE_URL`，认证模式默认 `jwt`，且构建阶段拒绝空 API 地址或未知认证模式。
- Web 镜像记录 API 地址与认证模式标签，外部发布前可对不可变镜像进行核对。
- 开发 Compose 显式 opt-in `dev` 认证，并同时允许 `localhost` 与 `127.0.0.1` 的本机 Web 来源。
- 开发 Compose 与 staging 统一使用可覆盖的 Python/npm 镜像源参数。
- Next.js 自动生成的代理说明文件纳入版本控制，工作区不再因重复生成而变脏。

## 验证证据

- Python：65 passed，6 skipped；跳过项仅为本地未直连的 PostgreSQL 专项测试。
- Ruff：通过。
- `pip check`：通过。
- Streamlit 包检查：未安装。
- Next.js ESLint、TypeScript 与 production build：通过。
- 开发与 staging Compose 配置：通过（staging 使用测试专用非生产密钥校验）。
- Docker 开发栈：PostgreSQL、Redis、API、Worker、Web 均成功启动；API 与依赖健康检查通过。
- 真实浏览器 E2E：Next.js → FastAPI → PostgreSQL → Redis/Dramatiq → SSE → 独立验证全链路通过，浏览器异常为 0。
- E2E 截图：`artifacts/e2e/clean-architecture-final-20261011.png`（本地证据，不提交运行时产物）。

## 边界

GitHub Pages 继续作为静态演示站，不承载外部 API。完整 API 功能通过容器化 Web/API 部署提供。此次收口不构成 Production Candidate 宣告，后续仍需独立 Production Readiness Gate。
