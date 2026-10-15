# Gate C2 未解决事项与风险

## 报告元数据

- 项目：HAHA 非遗图文脚本创作与视频内容社区平台
- 升级主题：Community Gate C2
- 报告状态：`COMPLETE`
- 时间：2026-10-15 20:09（Asia/Shanghai）
- 已测试实现提交：`55e0326b9c77ce1a17665afe1ad29fcaa3e15188`
- 分支：`main`
- Owner：除非单项另有说明，当前均为 `UNKNOWN`

## 状态定义

- `OPEN`：已确认存在，尚未纳入本轮。
- `UNKNOWN`：缺少执行证据，不能推断通过。
- `BLOCKED`：存在外部阻断，当前无法推进。
- `RESOLVED`：原风险已由可复核执行证据关闭；保留条目用于追溯。

本轮没有把任何下列事项包装为 Production Ready。

## 风险登记表

| ID | 风险 | 类型 | 严重度 | 证据/影响 | 缓解与目标条件 | Owner | 状态 |
|---|---|---|---|---|---|---|---|
| C2-R01 | 正式媒体链路缺失 | 正确性/安全/成本 | HIGH | 当前只存素材元数据，不能承载真实视频发布 | 对象存储、扫描、探测、转码、删除与成本验收 | UNKNOWN | OPEN |
| C2-R02 | 正式文化事实审核缺失 | 数据完整性/IP | HIGH | `demo_seed` 与 pending trust 不能作为正式文化结论 | 来源授权、专家/传承人复核、撤稿机制 | UNKNOWN | OPEN |
| C2-R03 | Gate E 未完成 | 权限/治理 | HIGH | 只有 C2 最小审核状态机 | 统一队列、二审、申诉、下架、审计治理 | UNKNOWN | OPEN |
| C2-R04 | staging JWT 浏览器未测 | 安全/部署 | HIGH | 仅单元 JWT 与 development Docker Chrome | staging + JWT + HTTPS 全链复审 | UNKNOWN | UNKNOWN |
| C2-R05 | 精确实现 SHA 的远端 CI | 部署 | HIGH | `55e0326` 的 CI `38730701104` 与 Pages `38730701111` 均成功 | 保持分支保护并保留 Actions 构件 | Codex/User | RESOLVED |
| C2-R06 | C2 写限流未启用 | 安全/容量 | MEDIUM | API 预留 429，尚无执行证据 | 用户/IP/工作区配额与告警 | UNKNOWN | OPEN |
| C2-R07 | 搜索规模有限 | 性能/维护 | MEDIUM | 当前为小目录确定性检索 | 用真实语料和容量评测决定 FTS/搜索服务 | UNKNOWN | OPEN |
| C2-R08 | 全局互动数为演示口径 | 正确性 | MEDIUM | 个人状态权威，全局基线非实时聚合 | 增加聚合与数据口径标识 | UNKNOWN | OPEN |
| C2-R09 | 导入不是整批单事务 | 数据完整性/恢复 | MEDIUM | 可幂等重试，但进程中断可部分完成 | 事务边界或显式可恢复导入作业 | UNKNOWN | OPEN |
| C2-R10 | 审计无数据库级防篡改 | 安全/合规 | MEDIUM | 应用追加式，DB 特权仍可修改 | 最小权限、保留与外部审计 | UNKNOWN | OPEN |
| C2-R11 | 容量与故障恢复未量化 | 性能/恢复 | MEDIUM | 无 P95/P99、soak、故障注入 | 压测、故障演练、RPO/RTO | UNKNOWN | UNKNOWN |
| C2-R12 | TestClient 弃用告警 | 依赖/维护 | LOW | 测试完成但有一条上游告警 | 在兼容升级窗口处理 | UNKNOWN | OPEN |
| C2-R13 | Windows 临时目录权限 | 维护 | LOW | 需显式 `--basetemp` | 统一测试临时目录 | UNKNOWN | OPEN |
| C2-R14 | 恢复未做逐行哈希 | 恢复/数据完整性 | MEDIUM | 关键计数与服务正常，完整等价未知 | 测试 DB 硬门禁 + 全表校验 | UNKNOWN | UNKNOWN |

目标日期：除 C2-R05 已关闭外，其余各项当前均为 `UNKNOWN`，应由后续 Gate 规划明确负责人和日期。

## 高优先级

### 1. 正式媒体链路 — OPEN

C2 投稿只保存图片/视频/文档的元数据，并在 UI 明确标注“不会上传文件”。尚无对象存储、分片上传、MIME 嗅探、恶意文件扫描、FFprobe、转码、封面提取、CDN、删除和保留策略。比赛演示可使用元数据闭环，不能解释为真实视频发布基础设施。

### 2. 正式文化目录和事实审核 — OPEN

当前服务端目录为版本化 `demo_seed`，人物为虚构演示人物，事实状态为 pending。发布投稿仍以 pending trust 进入 Feed。正式来源授权、传承人确认、专家审核、争议处理和撤稿机制尚未完成。

### 3. Gate E 统一审核后台 — OPEN

C2 只实现投稿所需最小 reviewer/admin 状态机，不等于四模块统一审核。审核领取、队列分配、二审、申诉、利益冲突、不可变审计权限、内容下架和跨模块工单仍属于 Gate E。

### 4. Staging JWT 真实浏览器验证 — UNKNOWN

代码级 JWT fail-closed 与 C2 JWT 契约已通过；最终 Docker/Chrome 运行的是显式 development auth，且端口只绑定回环。尚未在独立 staging、真实 JWT Cookie/BFF 会话、反向代理和 HTTPS 下重跑整套浏览器场景。

### 5. 精确提交远端 CI — RESOLVED

实现已提交为 `55e0326b9c77ce1a17665afe1ad29fcaa3e15188` 并推送到 `origin/main`。GitHub Actions `HAHA CI` 运行 `38730701104` 全部 Job 成功，其中 `community-e2e` 明确执行 C2 API 和 C2 浏览器步骤；Pages 运行 `38730701111` 的构建、部署和 smoke test 成功。初始提交 `bf39263` 的失败运行仍保留在证据链中，没有被隐藏。

## 中优先级

### 6. 写入限流与滥用防护 — OPEN

API 契约预留 429，但 C2 评论、注释、互动和投稿端点尚未接入可配置限流。内部测试需限制可信用户；外部访问前必须补齐用户/IP/工作区维度配额和告警。

### 7. 搜索规模与中文检索质量 — OPEN

当前检索读取工作区目录后做确定性匹配和排序，适合小规模内部目录。没有中文分词、同义词、拼音、召回评测、索引增量或大数据分页性能证据。是否需要 PostgreSQL FTS 或独立搜索服务应由容量和质量评测决定。

### 8. 互动聚合数字 — OPEN

浏览者自己的收藏、想学、致意和观看状态是服务端权威；`demo_seed` 展示的全局浏览/互动数字仍是演示基线，不是实时聚合。正式展示前需增加聚合查询或异步计数，并标明数据口径。

### 9. 本地档案跨仓储原子性 — OPEN

迁移写入使用稳定 ID、目标校验、幂等 upsert 和最终 receipt，可安全重试；但 User Center 与 Community 目前通过独立仓储连接逐项写入，不是一个覆盖整批导入的数据库事务。进程中断可能留下部分成功、无 receipt 的状态，重试会收敛但不是全有或全无。

### 10. 审计的数据库级防篡改 — OPEN

应用只追加 `community_submission_events`，并把投稿当前态、版本和事件同事务提交；数据库角色仍可能直接修改或删除事件。正式审计需最小权限数据库账号、写保护策略、保留周期和外部审计导出。

### 11. 容量、性能和故障恢复 — UNKNOWN

尚无并发用户容量、P95/P99 延迟、长时间 soak、Redis/PostgreSQL 故障注入、跨区恢复或 RPO/RTO 证据。已有并发测试只验证关键原子性，不等于负载验收。

## 低优先级与维护项

### 12. 测试依赖弃用告警 — OPEN

Starlette 提示当前 `httpx` TestClient 集成将弃用，后续应按上游兼容矩阵升级，不宜在 C2 中盲目追新。

### 13. Windows 测试临时目录权限 — OPEN

系统 `E:\Temp\pytest-of-13306` 存在权限问题。最终测试通过显式项目 `--basetemp` 执行。应清理历史受保护测试目录并在开发脚本中统一专用临时目录。

### 14. 恢复一致性审计 — UNKNOWN

误执行会清空开发库的集成 fixture 后，已从迁移前 dump 恢复并验证关键计数、迁移 head 与服务健康；没有执行全表逐行哈希比对，因此不能证明每条非关键记录语义等价。今后禁止集成 fixture 接受开发数据库 URL，并应加入数据库名/项目标识硬门禁。

## Production Readiness Gate 复审所需证据

1. 新 Git SHA 和 GitHub Actions 全绿记录：C2 已提供；后续 Production Gate 仍需以届时精确候选 SHA 重新执行。
2. 独立 staging，`HAHA_ENVIRONMENT=staging`、JWT、HTTPS、反向代理与安全响应头证据。
3. 无凭据、伪造 header、过期/撤销 token、跨工作区和角色矩阵的真实 HTTP/浏览器负向测试。
4. C2 写端点限流、审计告警和滥用场景测试。
5. 正式媒体上传、扫描、探测、转码、存储和删除证据，或明确保持功能关闭。
6. 正式文化数据来源、授权和事实审核抽样报告。
7. 备份恢复演练、全表一致性校验、明确 RPO/RTO 和回滚步骤。
8. 目标容量下的 P95/P99、错误率、资源曲线与 1 小时以上稳定性结果。
9. 依赖/镜像漏洞扫描、SBOM、秘密扫描和日志脱敏结果。
10. Gate E 审核治理完成证据，或明确限制 C2 只供受控内部测试。

在以上关键项完成前，不应宣布 Production Candidate。
