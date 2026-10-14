import type { Metadata } from "next";

import { IdentityCenter } from "./IdentityCenter";

export const metadata: Metadata = {
  title: "用户中心 · 身份与文化成长空间｜HAHA",
  description: "统一管理 HAHA 多身份、文化档案、工作台和真实业务任务。",
};

export default function IdentityCenterPage() {
  return <IdentityCenter />;
}
