import type { Metadata } from "next";

import { CommerceProductDetail } from "./CommerceProductDetail";

export const metadata: Metadata = {
  title: "商品详情｜HAHA 非遗好物",
  description: "查看商品信息、来源说明与可信边界。",
};

export default async function CommerceProductPage({ params }: { params: Promise<{ productId: string }> }) {
  const { productId } = await params;
  return <CommerceProductDetail productId={productId} />;
}
