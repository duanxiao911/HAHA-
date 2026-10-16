import type { Metadata } from "next";
import "./styles.css";
import "./p0.css";
import "./community.css";
import "./demo.css";
import "./design-system.css";
import "./community-v2.css";
import "./community-product.css";
import "./product-pages.css";
import "./identity-center.css";
import "./learning-ux.css";
import "./commerce.css";
import "./platform-home.css";
import { CommunityProvider } from "@/lib/community";

export const metadata: Metadata = {
  title: "HAHA 非遗文化平台",
  description: "连接视频社区、非遗电商、文化学习与统一身份成长空间。",
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <a className="skipLink" href="#main-content">跳到主要内容</a>
        <CommunityProvider>{children}</CommunityProvider>
      </body>
    </html>
  );
}
