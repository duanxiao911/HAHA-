# G1 用户中心真实闭环｜功能验收报告

- 项目：HAHA
- 状态：COMPLETE
- 时间：2026-10-14（Asia/Shanghai）
- Git：`5a5fa4f`，`main`，DIRTY（被测状态含未提交变更）
- 环境：本机 Docker 真实栈 + PostgreSQL/Redis/API/Worker/Next.js + Headless Chrome
- 验收结论：PASS（仅针对 G1 范围）；不代表 Production Candidate。

## 需求映射

| 验收项 | 实现 | 证据 | 结果 |
|---|---|---|---|
| 今日聚合 | `/api/user-center` + Today UI | 三屏浏览器 E2E | PASS |
| 文化资产跨刷新恢复 | library 表/API + 内容详情同步 | 真实 Chrome 连续收藏/想学/稍后看并回到中心 | PASS |
| 观看历史与退出 | history API + preferences | 真实 API 关闭历史后写入为空 | PASS |
| 账户资料 | profile PATCH + 设置表单 | 保存后刷新显示“真实浏览器体验员/贵州” | PASS |
| 消息已读 | notification owner scope | 浏览器已读 + 跨用户 404 单测 | PASS |
| 多身份不越权 | 复用 IdentityService | 既有身份测试 + G1 聚合显示 | PASS |
| PostgreSQL 迁移 | Alembic 0007 | `alembic_version=20261014_0007` | PASS |
| 响应式 | 390/768/1440 | scrollWidth 等于 viewport | PASS |

## 执行证据

- `.venv\Scripts\python.exe -m ruff check src tests scripts`：exit 0，All checks passed。
- `.venv\Scripts\python.exe -m pytest tests -q`（允许系统临时目录）：exit 0，`76 passed, 7 skipped`；唯一警告为 FastAPI TestClient 的上游弃用提示。
- `npm run lint`：exit 0。
- `npm run build`：exit 0；TypeScript 完成，52 个静态页面生成。
- `docker compose up -d --build`：exit 0；API/PostgreSQL/Redis/Worker healthy，Web running。
- PostgreSQL：`alembic_version=20261014_0007`；目标用户文化资产计数为 3。
- `python scripts/e2e_user_center_gate_c1.py`：exit 0；3 屏、12 项业务断言、0 浏览器异常。
- `python scripts/e2e_community.py`：exit 0；社区五屏与内容—搜索—投稿—审核—通知回归全部通过，0 浏览器异常、0 失败响应。

浏览器证据：`artifacts/e2e/user-center-g1/report.json` 及 `user-center-390.png`、`user-center-768.png`、`user-center-1440.png`、`user-center-final.png`。

## 状态、负向与恢复

- Loading/Error/Empty：页面均有显式状态；API 断开可重新连接。
- 非法资产类型、外链：400。
- 他人通知：404。
- 重复收藏/关注/观看：不重复建行。
- 页面刷新：资料、文化资产、已读状态均恢复。
- 数据库不可用恢复、并发压测与备份恢复：UNKNOWN，未纳入 G1 内部测试范围。

## Production Readiness Gate

G1 功能门禁 PASS；整个平台 Production Readiness 为 PARTIAL。尚缺正式 JWT 用户接入演练、容量/并发、备份恢复、观测告警以及云端部署复审，因此本报告不宣布 Production Candidate。

