# HAHA Phase D 社区闭环升级与真实环境验收报告

日期：2026-10-12

基线分支：`main`

实现起点：`1e0f836`

## 1. 结论

本轮完成了“真实内容 API 接入前”的社区产品闭环升级，并在本机完整 Docker 栈与真实 Chrome
中通过验收。新增能力均建立在现有 Next.js、FastAPI、PostgreSQL、Redis 与 Dramatiq 架构上，
没有恢复 Streamlit，也没有新增第二套前端或普通产品后端技术栈。

本轮没有接入真实账号、真实内容 API、对象存储、正式审核后台或真实视频流；所有社区身份、
投稿、审核、通知和互动均明确标记为本地演示。当前状态不是 Production Candidate，且没有执行
独立 Production Readiness Gate。

## 2. 完成范围

### 2.1 统一社区数据边界

- 建立内容、项目、人物、地区、来源、事实、评论、知识注释、通知与投稿的 TypeScript 类型。
- 建立可替换的 `CommunityAdapter` 契约；页面只依赖契约和 Provider，不直接依赖种子数组。
- 当前 `LocalCommunityAdapter` 只持久化用户产生的增量状态，种子资料保持只读。
- 本地状态包含 schema version、workspace、viewer 与恢复提示，为后续 API Adapter 留出边界。
- 四个人物全部明确标记为虚构演示人物，避免把演示档案误认为真实传承人资料。

### 2.2 内容与发现闭环

- 首页 Feed：推荐、关注、附近、正在学习及对应空状态。
- 内容详情：媒体占位、关键事实、来源清单、关联项目/人物/地区、时间点知识注释。
- 互动：致意、收藏、想学、稍后看、关注、观看历史、评论与知识注释。
- 搜索：内容、项目、人物、地区分类结果，相关度排序、历史记录、空态与错误态。
- 个人文化档案：收藏、想学、历史、关注、投稿与知识贡献。
- 消息中心：审核消息、已读、全部已读、删除和分类过滤。

### 2.3 关系网络与策展页面

- 非遗项目库及项目详情。
- 传承人与手艺人列表及人物详情；人物均为演示身份。
- 文化地图与地区深链，支持从项目、人物和搜索结果直接选中地区。
- 专题策展和内部演示活动页面。
- 内容、项目、人物、地区、专题与活动之间均使用真实存在的路由互相跳转。

### 2.4 创作、投稿、审核与发布回流

- AI 创作结果可转入投稿向导。
- 六步投稿向导：类型、素材登记、基础信息、关系/来源、AI 披露与检查、预览提交。
- 浏览器端只登记文件元数据，不伪装为真实文件上传。
- 投稿状态机覆盖草稿、检查、修改、提交、审核、通过、排期、发布、拒绝与归档。
- 独立本地审核台可填写审核意见，并将通过/发布结果回流到消息中心。
- 非法状态跳转由 Adapter 拒绝。

### 2.5 UI/UX 与可访问性

- 统一 App Header、移动底栏、状态提示、内容卡、实体卡、可信徽章与互动栏。
- 补齐项目、人物、地图、专题与活动 21 个页面级样式钩子。
- 手机端保留可信核验徽章，不再隐藏产品核心信任信息。
- 按钮与主要控件保持最小 44px 交互高度，并提供可见焦点。
- 加载、空、错误、离线、无权和限流状态拥有统一组件边界。
- 修复 Next.js 首屏水合竞态、固定时区文本差异、旧地区搜索路径和缺失 favicon 请求。

## 3. 自动化与 CI 升级

- 新增社区数据契约测试，覆盖互动幂等、关注/学习/历史、跨实体搜索、评论/知识注释和投稿状态机。
- 新增 `scripts/e2e_community.py`，直接驱动真实 Chrome DevTools Protocol，不依赖模拟 DOM。
- E2E 报告记录视口、横向溢出、页面指标、断言、浏览器异常和失败网络请求。
- GitHub Actions 前端作业新增社区契约测试。
- GitHub Actions 新增完整 Docker 栈社区浏览器 E2E 作业及失败日志、截图证据上传。
- GitHub Pages 构建新增契约测试，部署后新增 HTTP/内容冒烟检查。
- `websockets` 已显式加入开发测试依赖，不再依赖本机偶然安装。

上述 CI 配置已在本地通过 YAML 解析和命令级验证；新增作业的 GitHub runner 结果需以本轮
提交推送后的远端 Actions 为准，不能用旧基线的绿色记录替代。

截至 2026-10-12，远端 `origin/main` 的最近一次 HAHA CI 与 Pages 部署均在提交 `3d4cb22`
成功（Actions runs `38088734661`、`38088734703`）；它们只证明旧远端基线，不覆盖本轮
`1e0f836` 之后的未提交工作区。

## 4. 真实环境证据

测试环境：本机 Docker Compose 完整栈，Web/API 仅绑定 `127.0.0.1`，PostgreSQL 与 Redis 不映射
宿主公网；浏览器为真实无头 Chrome。

| 验收项 | 结果 |
|---|---|
| Ruff（`src tests scripts`） | PASS |
| ESLint | PASS，0 error |
| TypeScript `--noEmit` | PASS |
| 社区契约测试 | PASS，5/5 |
| 后端 pytest | PASS，65 passed，6 skipped |
| Next.js production build | PASS，51 个静态/SSG 页面 |
| GitHub Pages 静态导出 | PASS，51 个页面 |
| Docker Web/API/PostgreSQL/Redis/Worker | PASS，服务健康 |
| 首页响应式矩阵 | PASS，390/768/1024/1280/1440 |
| 首页横向溢出 | 5/5 为 0px |
| 实体页视觉矩阵 | PASS，13 个页面/宽度组合 |
| 地图地区深链 | PASS，URL 正确选中云南 |
| 收藏与刷新持久化 | PASS |
| 收藏回流个人档案 | PASS |
| 搜索内容与项目 | PASS |
| 投稿素材/表单/来源/检查 | PASS |
| 投稿→审核→通过→发布 | PASS |
| 发布消息回流 | PASS |
| 浏览器异常 | 0 |
| HTTP 失败请求 | 0 |
| 既有 Creator API/Worker E2E | PASS，SSE、证据、验收与参数一致 |

证据文件（本地产物，不提交 Git）：

- `artifacts/e2e/community/report.json`
- `artifacts/e2e/community/console-errors.json`
- `artifacts/e2e/community/390.png` 至 `1440.png`
- `artifacts/e2e/community/projects-*.png`
- `artifacts/e2e/community/project-detail-*.png`
- `artifacts/e2e/community/inheritor-*.png`
- `artifacts/e2e/community/map-*.png`
- `artifacts/e2e/community/topics-*.png`
- `artifacts/e2e/community/events-*.png`
- `artifacts/e2e/phase-d-creator-regression.json`
- `artifacts/e2e/phase-d-creator-regression.png`

## 5. 真实 API 接入边界

下一步接入真实 API 时，应新增服务端 `CommunityAdapter` 实现并保持页面契约不变。至少需要：

1. OIDC/JWT 真实身份、工作区成员关系和角色权限；
2. 内容、项目、人物、地区、来源与事实的读 API；
3. 收藏、想学、历史、关注、评论、知识注释与通知的写 API；
4. 对象存储预签名上传、媒体处理与安全扫描；
5. 投稿审核、版权/授权、事实核验和发布的服务端状态机；
6. 搜索索引、分页游标、幂等键、限流、审计日志和错误码；
7. 真实视频播放与转码，不得把前端文件元数据登记当作上传成功。

本地 Adapter 可以继续作为离线演示和 UI 回归夹具，但生产构建必须由环境配置显式选择服务端
Adapter；若真实 API 配置缺失，应 fail-closed，不得静默回退为可写本地演示。

## 6. 剩余风险与下一门禁

- 当前社区数据不是权威非遗名录，演示来源仍需逐条接入服务端核验记录。
- 本轮未部署到用户的阿里云 ECS；没有 SSH 凭据、域名、TLS 和远端 secrets 证据。
- 当前没有真实账号、多端同步、对象存储、媒体转码、内容审核人员体系和反滥用系统。
- 尚未执行负载、长稳、断网恢复、容量、渗透测试与云端备份恢复演练。
- 新增 GitHub CI 作业必须在提交并推送后取得远端绿色 run，才可列为远端证据。
- 真实 API 接入完成后，必须另行执行独立 Production Readiness Gate。

## 7. 状态判断

Phase A：保留并回归通过。

Phase B：保留并回归通过。

Phase C：保留并回归通过。

Phase D（真实 API 前的社区本地闭环）：本轮实现并在本机真实 Docker/Chrome 环境通过。

Production Candidate：未宣布，尚未达到独立门禁条件。
