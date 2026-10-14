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
import { CommunityProvider } from "@/lib/community";

export const metadata: Metadata = {
  title: "HAHA 非遗创作平台",
  description: "可追踪、可验证的非遗内容创作工作台",
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
