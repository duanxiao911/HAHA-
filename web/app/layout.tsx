import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "HAHA 非遗创作平台",
  description: "可追踪、可验证的非遗内容创作工作台",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
