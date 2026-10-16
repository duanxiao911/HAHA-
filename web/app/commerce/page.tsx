import type { Metadata } from "next";
import { Suspense } from "react";

import { StateNotice } from "@/components/community/StateNotice";
import { CommerceCenter } from "./CommerceCenter";

export const metadata: Metadata = {
  title: "非遗交易沙盒｜HAHA",
  description: "内部验证商品审核、库存、订单、沙盒支付、履约与售后闭环。",
};

export default function CommercePage() {
  return <Suspense fallback={<StateNotice kind="loading" title="正在打开交易沙盒" description="准备账户、商品和订单状态。" />}><CommerceCenter /></Suspense>;
}
