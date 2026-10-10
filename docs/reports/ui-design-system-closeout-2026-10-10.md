# HAHA Web UI 基础规范补完报告（2026-10-10）

## 范围

本轮延续 2026-10-04 的 P0 UI audit，只补齐 Web UI 基础规范，不删除现有功能，不改变
社区页与 AI 创作台的信息架构，也不新增业务能力。

## 已完成

- 新增共享 Design Token：语义颜色、4px 间距体系、字体基础、圆角、阴影、页面宽度、焦点、
  z-index，集中在 `web/app/design-system.css`。
- 页面最大宽度统一为 1520px，桌面安全边距为 24–48px；社区 Header、Hero、内容区和创作台
  Header、流程导航、主内容共享边界。
- 创作台正文和控件从 8–12px 的密集小字号提升到 12–14px 基础阅读层级；标题、卡片标题、
  Meta 信息重新形成清晰层级。
- Input / Select 统一为最小 44px，Textarea 最小 96px；按钮统一为至少 40px 点击高度，并
  共享品牌 Focus Ring、Disabled 状态和 Hover 状态。
- Panel / Card / Control 收敛为 16 / 12 / 8px 圆角层级；普通卡片不再叠加重阴影，页面仅保留
 两级阴影。
- 社区页保留编辑型视觉，但移除 Hero 卡片旋转，降低过度装饰；内容卡、导航和行动按钮与产品
  Token 对齐。
- 响应式补齐 1280、1024、768、480px：桌面保留双栏，平板收缩 Inspector，移动端变为
  工作区 → 创作设定 → 审核 → 运维的单列顺序。
- 增加跳到主内容链接、全局 `:focus-visible`、Escape 关闭抽屉、抽屉打开时锁定 Body、
  `aria-expanded` / `aria-controls` / dialog 语义及隐藏抽屉 inert。
- 增加长文本换行和 `prefers-reduced-motion` 支持。

## 当前判断

页面已经从“局部 P0 修补”升级为共享基础 Design System。社区页仍是内容发现页，创作台仍是
AI 工作台，两者不会被强行做成同一种页面，但颜色、栅格、控件、焦点和响应式规则已经统一。

## 暂不扩大的项目

- 尚未引入第三方组件库；当前规模下共享 Token 与现有语义类足够，避免扩大技术栈。
- 尚未把所有 JSX 拆为 Button、Input、Card 等独立 React 组件。下一次发生第二套交互实现时再
  抽取，以免只为形式增加组件层级。
- 未增加模型选择、知识库命令或新 Composer 功能；这些属于产品能力，不属于本轮基础规范。

## 验收

- ESLint：通过。
- Next.js production build、TypeScript、6 个静态页面生成：通过。
- `/`、`/community`、`/creator`：HTTP 200。
- Edge 实际截图：1440×900 社区页、1440×900 创作台、768×1024 创作台。
- 768px 创作台无横向布局压缩，主要操作保持可见；1440px 首屏可见页面身份、流程、工作区、
  审核状态和开始创作入口。

本报告不构成 Production Candidate 声明。
