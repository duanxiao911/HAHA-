# Gate C1 用户中心收口｜剩余问题与风险

- 状态：COMPLETE（Gate C1）；以下项目未被本轮证据消除
- 时间：2026-10-15（Asia/Shanghai）

| ID | 严重度 | 类型 | 证据与影响 | 缓解/目标 | 状态 |
|---|---|---|---|---|---|
| C1-R01 | MEDIUM | 内容一致性 | 社区内容目录、评论、注释和投稿仍含明确标记的本地适配数据；账户资产虽真实持久化，源内容不是完整内容 API | Gate C2 接入真实账户内容数据并迁移本地档案 | OPEN |
| C1-R02 | MEDIUM | 容量/性能 | 功能与并发首次建号已测，但没有持续并发、长历史列表和数据库索引压测 | 独立容量计划与阈值 | UNKNOWN |
| C1-R03 | MEDIUM | 恢复 | 迁移和持久化已测，未执行备份还原与灾难恢复演练 | 执行备份、恢复、RPO/RTO 证据 | UNKNOWN |
| C1-R04 | MEDIUM | 部署/观测 | 本机 Docker 和 GitHub CI 覆盖存在；云 ECS、TLS、域名、告警值守未在本轮验证 | Production Readiness Gate 单独复审 | UNKNOWN |
| C1-R05 | LOW | 依赖维护 | FastAPI TestClient 出现上游 `httpx` 适配弃用警告 | 后续依赖升级窗口迁移到 httpx2 | OPEN |
| C1-R06 | LOW | 测试维护 | Windows 受管沙箱对 pytest 临时目录有 ACL 限制；提升权限后 89 项通过 | CI/Linux 继续作为标准可复核环境 | MITIGATED |

安全/隐私/权限：本轮 JWT 真实回归为 PASS，但不替代独立渗透与配置复审。迁移/回滚：无新 schema，应用回滚可行；镜像级回滚未在本轮演练，`UNKNOWN`。成本、许可证与 IP：未增加依赖或付费调用，N/A。Owner 与目标日期：UNKNOWN，需由项目负责人排期。
