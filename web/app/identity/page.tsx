import type { Metadata } from "next";
import { Suspense } from "react";

import { StateNotice } from "@/components/community/StateNotice";
import { IdentityCenter } from "./IdentityCenter";

export const metadata: Metadata = {
  title: "用户中心 · 身份与文化成长空间｜HAHA",
  description: "统一管理 HAHA 多身份、文化档案、工作台和真实业务任务。",
};

export default function IdentityCenterPage() {
  return (
    <Suspense fallback={<StateNotice kind="loading" title="正在打开用户中心" description="准备账户视图与导航状态。" />}>
      <IdentityCenter />
    </Suspense>
  );
}
