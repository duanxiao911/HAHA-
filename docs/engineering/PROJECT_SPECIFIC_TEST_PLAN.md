# Gate F 项目专属测试计划

## 自动化层级

| 层级 | 命令/场景 | 目的 |
|---|---|---|
| 静态 | `python -m ruff check src tests scripts`、`pnpm lint` | 语法、规范、危险遗漏 |
| 依赖审计 | `pip-audit --local`、`pnpm audit --prod` | 阻断生产依赖已知漏洞 |
| 单元/契约 | `python -m pytest -q`、前端两套 contract | 安全配置、阈值与模块回归 |
| AI Eval | `python scripts/run_ai_eval.py` | 保持创作链 golden gate；不代表 AI 老师已接通 |
| PostgreSQL | Alembic head + integration tests | 真实数据库、事务、并发与权限 |
| 恢复 | `postgres_restore_drill.py` | 当前 schema 逻辑备份、隔离恢复与一致性 |
| 容量 | `production_load_gate.py` | 错误率、P95、P99 阈值 |
| 浏览器 | C1/C2/C3/D/E 与 G3/G4 | 用户链路、会话、响应式与持久化 |
| 发布 | preflight + smoke + rollback rehearsal | 配置、镜像、TLS/CORS、回滚 |

## 本地容量基线

CI/本机默认只读 `/ready`：100 请求、并发 10、错误率 0、P95 ≤ 750 ms、P99 ≤ 1500 ms。
该阈值用于发现明显回归，不是生产 SLO。外部 staging 必须用预期拓扑、数据规模和网络重新基准。

## 恢复验收

1. 源库可读取当前 Alembic revision 和关键表。
2. dump 非空且 `pg_restore -l` 可读。
3. 新隔离库恢复成功。
4. revision 与所有验证表计数完全一致。
5. 隔离库和容器临时文件按策略清理；报告保留散列、大小和耗时。

## 失败处理

任何安全、迁移、恢复、权限或真实浏览器失败均为 Gate F 阻断；不得以 Mock、重跑后忽略或文档说明
替代修复。外部依赖未提供时记录 `BLOCKED`，未执行项记录 `UNKNOWN`。
