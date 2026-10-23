# S10 图片创作切片架构边界

状态：`PARTIAL / REAL_MODEL_BLOCKED`（2026-10-22）。工程链已实现；当前运行环境未配置 `ARK_API_KEY`，因此真实 Seedream 输出验收尚未执行，不能关闭 S10。

## 决策

- 图片任务复用既有 `Project → BriefVersion → Run`、Run 租约、Redis/Dramatiq 与 creator/contributor 授权，不建立第二套任务系统。
- `image_generation_requests` 保存与已复核 S09 脚本绑定的类型化输入；创建 Run 与请求必须同事务。
- `creator_image_assets` 保存不可变版本、工作空间归属、文件哈希、尺寸、来源主机和模型调用证据。浏览器不是事实源。
- Worker 只接受真实 Seedream 路由。缺少密钥返回明确失败；不生成模板图或占位图。
- 供应商结果只允许从配置白名单内的 HTTPS 主机下载，限制重定向、20 MB 响应和 4000 万像素；PNG/JPEG 必须完整解码，服务端重新计算 SHA-256 后才能进入资产表。
- 文件先原子提交到与 API 共享的持久媒体卷；数据库最终提交失败时补偿删除本次文件。
- 参考图与编辑虽然 Router 有参数能力，但在供应商账号真实实测前 API 固定拒绝，UI 明确显示关闭。

## API

- `GET /api/creator/model-capabilities`：返回图片能力、模型、限制与参考图门禁。
- `POST /api/creator/image-runs`：创建与已复核脚本绑定的幂等图片任务；未配置真实能力返回 503。
- `GET /api/runs/{run_id}`：图片任务附带请求快照与资产版本。
- `GET /api/projects/{project_id}/image-assets`：工作空间授权后的项目画廊。
- `GET /api/creator/image-assets/{asset_id}/content`：私有、无缓存的授权文件读取。

## 迁移与回退

Alembic `20261022_0022` 只新增两张 S10 表与查询索引，不修改 S09 数据。降级会删除 S10 表，因此含真实资产的环境应先导出数据库记录与媒体卷并采用镜像/兼容 Schema 回退，不应直接对生产数据执行 destructive downgrade。

## 尚未关闭

- 真实 Seedream 请求、图片下载、完整解码和请求 ID 证据：`BLOCKED`（缺少 ARK 密钥）。
- 参考图/编辑：`BLOCKED`（账号能力未实测）。
- 病毒与内容安全服务、对象存储、CDN、配额计费：留给生产门禁，不由 MIME/解码检查冒充。
