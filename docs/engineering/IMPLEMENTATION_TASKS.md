# Gate F 实施任务矩阵

| ID | 任务 | 状态 | 证据 |
|---|---|---|---|
| F-01 | 扫描运行架构、CI、恢复、发布与可观测资产 | PASS | 本目录架构与计划 |
| F-02 | 保护共享环境 `/metrics` | IMPLEMENTED | `test_observability.py` |
| F-03 | 发布预检要求独立指标密钥 | IMPLEMENTED | `test_release_preflight.py` |
| F-04 | 发布烟测覆盖指标匿名拒绝与授权访问 | IMPLEMENTED | `release_smoke.py` |
| F-05 | 增加量化容量阈值脚本 | IMPLEMENTED | `production_load_gate.py` |
| F-06 | 增加当前 schema 隔离恢复演练 | IMPLEMENTED | `postgres_restore_drill.py` |
| F-07 | CI 纳入 Gate E、容量与恢复 | IMPLEMENTED | `.github/workflows/ci.yml` |
| F-08 | 运行本机 PostgreSQL/Redis/API/Web 全链验证 | PASS | `artifacts/e2e/gate-f-load.json`、`artifacts/recovery/gate-f-restore.json` |
| F-09 | GitHub CI 验证当前提交 | PENDING | Actions run URL |
| F-09A | 修复生产依赖高危公告并持续审计 | PASS | Next 16.3.8、source-map-js 1.2.2、pip 26.2.1；生产审计 0 |
| F-10 | 外部 HTTPS staging 部署与回滚 | BLOCKED | 需要域名、ingress、镜像仓库和授权 |
| F-11 | 告警真实投递与值班确认 | BLOCKED | 需要监控平台和值班渠道 |
| F-12 | 加密异地备份与 PITR | BLOCKED | 需要备份存储、KMS 与 PostgreSQL 运维环境 |
| F-13 | ESLint 间接依赖 `braces` 高危公告 | OPEN | 仅开发依赖、生产审计不包含；上游暂无修复版，持续监控 |

状态必须随真实执行证据更新；“代码存在”不等于“运行通过”。
