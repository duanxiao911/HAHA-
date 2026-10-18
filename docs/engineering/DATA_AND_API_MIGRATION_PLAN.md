# Gate F 数据与 API 迁移计划

## 数据库边界

Gate F 首批增强不新增表、列、索引或约束，因此不创建 Alembic revision。当前期望 head 为
`20261016_0012`。发布仍先执行 `alembic upgrade head`，不得跳过迁移前备份。

## 恢复兼容策略

- 使用 PostgreSQL custom-format (`pg_dump -Fc`)。
- 恢复目标必须是新建的随机 `haha_restore_*` 数据库。
- 核对 `alembic_version` 以及 `users`、`memberships`、`projects`、`learning_profiles`、
  `quiz_attempts`、`community_entities`、`commerce_orders` 计数。
- 验证失败不修改源数据库，并阻断发布签署。
- 默认验证后删除隔离库；调试保留必须显式使用 `--keep-restore-db`。

这证明逻辑备份能恢复当前 schema 和选定跨模块记录，不证明跨区域灾备、PITR 或业务 RTO 已达标。

## API 契约变化

`GET /metrics`：

- development：保持本机无认证访问，兼容开发与测试。
- staging/production：要求 `Authorization: Bearer $HAHA_METRICS_TOKEN`。
- 无/错误凭据返回 `401` 与 `WWW-Authenticate: Bearer`。
- 成功响应增加 `Cache-Control: no-store` 与 `X-Content-Type-Options: nosniff`。

`/health`、`/ready` 与业务 API 不变。指标密钥必须至少 32 字符且不得等于 JWT 密钥。

## 回滚

代码回滚到前一不可变镜像前，先确认其可与当前 schema 共存。指标认证没有数据回滚动作；如旧监控
采集器尚未配置 Bearer token，应先更新采集器再切换 API。不得为兼容而在公网重新开放指标。
