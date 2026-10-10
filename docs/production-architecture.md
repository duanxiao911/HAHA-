# HAHA 生产架构迁移说明

## 当前阶段

仓库已完成 Web 外壳迁移，Next.js 是唯一正式前端。

已完成的生产核心：

- 框架无关的领域对象；
- 不可变参数版本；
- 机器可读 Run 状态机；
- 幂等创建 Run；
- 独立交付参数验证；
- 脚本与检索证据版本化；
- 持久化接口、SQLite 开发适配器和 PostgreSQL/SQLAlchemy 适配器；
- Alembic 可回滚迁移；
- Redis/Dramatiq Worker 边界与限次重试；
- 服务令牌认证边界与 workspace 隔离检查；
- FastAPI 接口入口。
- Next.js 正式前端骨架与完整容器化开发栈。

## 权威数据链

```text
Project
  └─ BriefVersion (immutable)
       └─ Run (state machine + idempotency key)
            ├─ Retrieval / model evidence
            ├─ Verification result
            └─ ScriptVersion (immutable)
```

页面显示值不再被视为业务权威。一次生成只读取其绑定的 `BriefVersion`，验证通过后才允许创建 `ScriptVersion`。

## 模块边界

- `haha_media`：可迁移的知识、模型和生成能力。
- `haha_core`：不依赖 Web 框架的领域规则、生命周期和持久化端口。
- `haha_api`：HTTP 输入校验和资源接口，不承载创作规则。
- `web`：Next.js 正式前端与社区、创作工作台页面。

## 生产前仍需完成

1. 接入真实 OIDC 身份提供方，替换过渡期服务令牌认证。
2. 增加数据库行级安全策略与成员/角色表。
3. 在真实 PostgreSQL、Redis 和 Docker 环境完成故障恢复及并发压测。
4. 增加对象存储、文件扫描和资产权限。
5. 增加 SSE 运行进度、取消和死信管理界面。
6. 建立结构化日志、指标、Trace、告警和审计记录。
7. 安装前端依赖并完成 Playwright 浏览器验收。
8. 建立预发布、生产环境和 CI/CD 发布门禁。

在以上事项完成前，不应把当前 API 标记为“生产就绪”。
