import type { Metadata } from "next";

import { CommerceAdvisor } from "./CommerceAdvisor";

export const metadata: Metadata = {
  title: "AI 智能导购｜HAHA 非遗好物",
  description: "通过真实商品目录对话寻找合适的非遗好物。",
};

export default function CommerceAdvisorPage() {
  return <CommerceAdvisor />;
}
