# G1 用户中心真实闭环｜遗留问题与风险

- 状态：COMPLETE（风险登记完成）
- 时间：2026-10-14（Asia/Shanghai）
- Git：`5a5fa4f`，DIRTY

| ID | 风险 | 类型/等级 | 证据与影响 | 缓解与目标 | Owner | 状态 |
|---|---|---|---|---|---|---|
| G1-R01 | 聚合读取暂无分页 | 性能 / MEDIUM | 单用户资产全部返回；规模增长会增加查询与响应体 | G2 为历史、消息、资产加入 cursor 分页并压测 | UNKNOWN | OPEN |
| G1-R02 | 评论与知识注释仍是浏览器本地数据 | 数据完整性 / MEDIUM | `CommunityAdapter` 仍负责这两类演示互动 | 后续 Community API Gate 服务端化；界面继续明确标注 | UNKNOWN | OPEN |
| G1-R03 | 正式 JWT 账户迁移未演练 | 权限/部署 / HIGH | 本机真实栈显式 dev auth；接口资源隔离已测，但未接真实身份提供方 | 接 API 前完成 JWT 签发、刷新、注销、角色映射 E2E | UNKNOWN | OPEN |
| G1-R04 | 备份恢复与 downgrade 未执行 | 恢复 / HIGH | 迁移前向成功；未进行破坏性回滚 | 在隔离快照上演练备份、恢复、迁移 downgrade/upgrade | UNKNOWN | OPEN |
| G1-R05 | 用户中心业务指标不足 | 可观测性 / MEDIUM | 有 HTTP 指标与日志，无资产写入失败率/延迟面板 | 增加业务计数、错误分类、SLO 与告警 | UNKNOWN | OPEN |
| G1-R06 | Windows 非提权 pytest 会被系统临时目录 ACL 拦截 | 维护 / LOW | 沙箱内 75 通过后 tmp_path 权限错误；允许系统临时目录后 76/7 全通过 | CI Linux 不受影响；本机文档固定可写临时目录或修复 ACL | UNKNOWN | OPEN |
| G1-R07 | FastAPI TestClient 上游弃用警告 | 依赖 / LOW | 完整测试有 1 条 StarletteDeprecationWarning | 跟踪 FastAPI/Starlette 官方迁移路径 | UNKNOWN | OPEN |

正确性、安全、迁移前向与社区回归均有 PASS 证据。成本无新增外部付费服务。许可证/IP 本轮无新增第三方素材或依赖，风险 N/A。Production Candidate 状态：未申请、未宣布。

