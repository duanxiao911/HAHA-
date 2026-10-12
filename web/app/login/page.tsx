import Link from "next/link";

import { ProductFrame } from "@/components/community/ProductFrame";

export const metadata = {
  title: "体验身份｜HAHA 非遗社区",
};

export default function LoginPage() {
  return (
    <ProductFrame>
      <div className="productSearchLayout">
        <section className="productPanel">
          <div className="productPanelBody">
            <small className="productEyebrow">LOCAL DEMO IDENTITY</small>
            <h1>先以本地体验身份继续</h1>
            <p>本轮暂不接入真实账号 API。收藏、关注、观看历史、评论和投稿草稿只保存在这个浏览器中，不会创建线上账户。</p>
            <div className="productInlineAlert">真实登录接入时将继续使用现有 JWT 与工作空间权限体系；前端隐藏按钮不能替代后端权限校验。</div>
            <div className="productFormActions">
              <Link className="productButton" href="/profile/demo-user">进入本地文化档案</Link>
              <Link className="productButtonSecondary" href="/">暂不登录，继续浏览</Link>
            </div>
          </div>
        </section>
        <aside className="productSidePanel">
          <h2>本地体验可以做什么</h2>
          <ul>
            <li>收藏、想学、致意和稍后看</li>
            <li>关注演示人物并查看关注 Feed</li>
            <li>保存搜索历史和观看进度</li>
            <li>创建投稿草稿并演示审核状态</li>
          </ul>
          <h2>暂时不能做什么</h2>
          <ul>
            <li>跨设备同步或找回数据</li>
            <li>代表真实身份提交或发布</li>
            <li>获得服务端权限与审计证据</li>
          </ul>
        </aside>
      </div>
    </ProductFrame>
  );
}
