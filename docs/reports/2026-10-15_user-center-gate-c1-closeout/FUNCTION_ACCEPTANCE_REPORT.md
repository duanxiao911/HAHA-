# Gate C1 用户中心收口｜功能验收报告

- 状态：PASS（仅 Gate C1）
- 时间：2026-10-15（Asia/Shanghai）
- Git：实现提交 `7523708`，`main`；执行测试时为与该提交代码等价的未提交工作树
- 环境：本机 Docker/PostgreSQL/Redis/API/Worker/Next.js + 独立 PostgreSQL 集成容器 + Headless Chrome

## 需求映射

| 用户结果 | 实现与入口 | 执行证据 | 结果 |
|---|---|---|---|
| 今日页成为账户中枢 | `/identity` 默认“今日” | 390/768/1440 浏览器断言 | PASS |
| 收藏、想学、稍后看跨刷新恢复 | 内容详情 → user-center library API | 三项真实 UI 写入并在文化资产恢复 | PASS |
| 关注与观看记录持久化 | follows/history API | UI 关注、自动历史、中心恢复 | PASS |
| 真实文化足迹和成长聚合 | `UserCenterService.snapshot` | 浏览器显示 + 单测字段断言 | PASS |
| 资料保存 | 设置页 profile PATCH | 保存、刷新、姓名/地区恢复 | PASS |
| 消息已读与删除 | notification API | UI 已读/删除；再次读取不复活 | PASS |
| 身份入口降级，专业工作台按角色显示 | 顶部账户菜单 | C1 三屏 + JWT G4 20 项断言 | PASS |
| 并发首次建号稳定 | 原子 insert-ignore | 独立 PostgreSQL 4 线程测试 | PASS |
| C2/C3/D/E 不冒充完成 | 页面能力边界文案 | 浏览器断言 Gate C3 边界 | PASS |

## 执行命令与结果

- `.venv\Scripts\python.exe -m pytest -q --basetemp=...`：exit 0，`89 passed, 12 skipped`；跳过项仅为需要独立 PostgreSQL URL 的组。
- 独立 PostgreSQL 17 + `alembic upgrade head` 后运行 `pytest tests/test_postgres_integration.py`：exit 0，`12 passed`，包含并发首次建号。
- `.venv\Scripts\ruff.exe check .`：exit 0，All checks passed；仅有受保护历史测试目录扫描警告。
- `pnpm lint`、`tsc --noEmit`：exit 0。
- `pnpm test:community`：exit 0，`5 passed`。
- `docker compose up -d --build`：exit 0；Next.js 编译、类型检查、55 个页面生成完成。
- `.venv\Scripts\python.exe scripts/e2e_user_center_gate_c1.py`：exit 0；3 个视口、18 项业务断言、0 浏览器异常。
- `.venv\Scripts\python.exe scripts/e2e_community.py`：exit 0；5 个视口及 13 个关联页面场景、18 项闭环断言，0 浏览器异常、0 HTTP 失败。
- JWT 栈下 `.venv\Scripts\python.exe scripts/e2e_role_workbench_g4.py`：exit 0；20 项断言、0 浏览器异常。

最初两次真实验收分别发现并修复：并发用户插入冲突、观看历史 effect 永久禁用按钮；早期失败不计为 PASS，最终结果以上述重跑为准。

## 状态与负向路径

Loading、Empty、Error、成功反馈和响应式状态均有实际页面覆盖。用户中心删除消息后再次 bootstrap 不重建；JWT 环境下 URL 查询角色不能提权；非专业身份不显示虚假工作台。AI Eval：N/A，本轮没有模型行为变更。

## Production Readiness Gate

Gate C1 功能门禁为 PASS。整个平台仍为 PARTIAL：没有执行云端部署、容量/压力、备份恢复、告警值守和独立安全复审。因此本报告不是 Production Candidate 或 Production Ready 声明。

证据：`artifacts/e2e/user-center-g1/report.json`、同目录四张截图，以及 `artifacts/e2e/role-workbench-g4/`、`artifacts/e2e/community/`。
