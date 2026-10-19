# Gate F 目标架构

状态：仓库与本地准发布门禁已通过；远端及外部发布门禁阻断

实施起点：`33a0e58`

范围：生产工程，不包含公开发布授权

## 决策

保持现有模块化单体，不引入第二套账户、权限、数据或部署技术栈：

- Web：Next.js，同源 BFF 持有 HttpOnly 会话。
- API：FastAPI，统一 membership 与多身份授权。
- Domain/Service/Repository：继续使用现有领域边界和依赖注入。
- Data：PostgreSQL 为服务端事实源，Alembic 单线迁移；SQLite 只作本地适配器。
- Async：Redis + Dramatiq。
- Delivery：不可变镜像、Compose 发布包、HTTPS ingress、发布预检与烟测。
- Supply chain：API/Worker/Migrate 使用 `/opt/haha-venv` 隔离 Python 包；Web 锁定已修复的
  Next.js 与传递依赖版本；Python 发布镜像和 CI 共用复核后的 Linux 运行时约束锁，生产依赖
  审计进入 CI。

## Gate F 增强边界

1. `staging/production` 的 `/metrics` 使用独立 Bearer 凭据；数据库、JWT 与指标凭据三者不得复用。
2. 发布预检、Compose、烟测与运维文档共享同一指标凭据、发布 ID 和完整 Git SHA 契约。
3. API 与 Web 镜像记录 OCI revision；`/health` 暴露非秘密 Git SHA，烟测核对发布 ID 与 SHA。
4. API 与动态 Web 壳统一输出基础安全响应头；不可信或超长请求 ID 由服务端替换。
5. API 使用 `/ready` 健康检查；Worker 同时验证进程与 Redis；Web 等待 API ready 后启动。
6. 容量烟测输出错误率、P50/P95/P99 并执行机器阈值判定。
7. PostgreSQL 恢复演练只恢复到随机隔离数据库，核对 revision 与 17 张跨模块关键表。
8. 媒体恢复演练核对 PostgreSQL 元数据、卷中文件、归档及隔离恢复后的大小和 SHA-256。
9. CI 纳入平台壳、浏览器、容量、PostgreSQL 恢复和真实媒体恢复门禁。

## 明确不做

- 不自动部署公网、staging 或 production。
- 不创建托管监控/告警账户，不虚构告警送达证据。
- 不替代 ingress 的 TLS、HSTS、WAF 与网络访问控制。
- 不将本机容量烟测外推为生产容量承诺。
- 不把内部复核 AI、单机媒体链或沙盒交易外推为正式教学、生产媒体处理或真实支付。

## 关键质量属性

- 安全：共享环境 fail closed；运维凭据职责分离；密钥不写入参数、日志或报告。
- 数据：恢复目标名称白名单；绝不覆盖源数据库；失败保留可诊断结果。
- 可恢复：备份目录、散列、大小、revision、表计数和耗时可审计。
- 性能：阈值由脚本返回码强制执行，不能只看人工截图。
- 可回滚：应用优先回滚镜像；schema 不兼容时恢复到新库后切换。

## 已知限制

- 当前指标是进程内计数器，多副本需外部采集聚合。
- 尚无托管告警、分布式追踪、跨主机加密备份和 PITR。
- 多副本 refresh token 竞争与分布式滥用控制仍需后续安全专项。
- 现有开发媒体卷有 5 个无数据库记录的历史测试文件；隔离准发布卷的一致性演练已通过，
  但开发卷在人工确认前不自动删除。
