import type { Metadata } from "next";
import { Suspense } from "react";

import { StateNotice } from "@/components/community/StateNotice";
import { CommerceCenter } from "./CommerceCenter";

export const metadata: Metadata = {
  title: "非遗好物｜HAHA",
  description: "发现非遗好物，查看清晰的来源与可信边界；交易功能当前处于内部沙盒。",
};

export default function CommercePage() {
  return <Suspense fallback={<StateNotice kind="loading" title="正在打开交易沙盒" description="准备账户、商品和订单状态。" />}><CommerceCenter /></Suspense>;
}
