# Gate F 实施任务矩阵

顺序状态：`REPOSITORY_PASS / REMOTE_AND_EXTERNAL_BLOCKED`（2026-10-19）。A–E 已先行收口；
Gate F 仓库实现和隔离准发布演练完成，但远端 CI 与外部环境门禁尚未满足。

| ID | 任务 | 状态 | 证据 |
|---|---|---|---|
| F-01 | 扫描运行架构、CI、恢复、发布与可观测资产 | PASS | 本目录架构与计划 |
| F-02 | 保护共享环境 `/metrics` | PASS | 单元测试 + 隔离发布烟测 |
| F-03 | 发布预检要求三类秘密独立、完整 SHA、不可变镜像 | PASS | `test_release_preflight.py` |
| F-04 | 发布烟测覆盖身份、CORS、指标、请求 ID 与提交绑定 | PASS | `release_smoke.py` 隔离栈全通过 |
| F-05 | 增加量化容量阈值脚本 | PASS | 隔离栈 `/ready` 500 请求、并发 25、错误率 0 |
| F-06 | 增加当前 schema PostgreSQL 隔离恢复演练 | PASS | revision `20261018_0015`、17 表一致 |
| F-06A | 增加媒体卷备份、元数据对账与隔离恢复 | PASS | 隔离栈 1 文件/1 记录、大小与 SHA-256 一致 |
| F-07 | CI 纳入 Gate E、容量、数据库及媒体恢复 | PASS（配置） | `.github/workflows/ci.yml`；远端执行见 F-09 |
| F-08 | 本机 PostgreSQL/Redis/API/Worker/Web 全链验证 | PASS | 准发布栈健康、烟测、恢复、容量和浏览器证据 |
| F-08A | 安全响应头、请求 ID 归一化、服务健康依赖 | PASS | API/Web 实测与 24 项聚焦测试 |
| F-08B | 完整后端、前端和真实浏览器回归 | PASS | 149 Python；6+4 前端契约；57 路由构建；G3 19 项 |
| F-08C | Python 发布依赖可复现约束与镜像 `pip check` | PASS | `constraints/runtime.txt`、Docker/CI 共用约束 |
| F-09 | GitHub CI 验证当前提交 | UNKNOWN | 当前提交尚未推送且本机 `gh` 认证无效 |
| F-09A | 生产依赖审计 | PARTIAL | 前端生产审计曾通过；本轮 Python/再次 npm 查询受网络阻断，需当前 CI 复核 |
| F-10 | 外部 HTTPS staging 部署与回滚 | BLOCKED | 需要域名、ingress、镜像仓库和授权 |
| F-11 | 告警真实投递与值班确认 | BLOCKED | 需要监控平台和值班渠道 |
| F-12 | 加密异地备份与 PITR | BLOCKED | 需要备份存储、KMS 与 PostgreSQL 运维环境 |
| F-13 | ESLint 间接依赖 `braces` 高危公告 | OPEN | 仅开发依赖、生产审计不包含；上游暂无修复版，持续监控 |
| F-14 | 开发媒体卷 5 个历史孤立文件处置 | OPEN | 不自动删除；需用户确认保留、归档或清理 |

状态必须随真实执行证据更新；“代码存在”不等于“运行通过”。
