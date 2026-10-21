import type { Metadata } from "next";

import { CommerceProductDetail } from "./CommerceProductDetail";

export const metadata: Metadata = {
  title: "商品详情｜HAHA 非遗好物",
  description: "查看商品信息、来源说明与可信边界。",
};

export function generateStaticParams(): { productId: string }[] {
  // The static demo has no authoritative commerce catalogue. Runtime API
  // deployments resolve real product ids dynamically; this route only keeps
  // the static exporter honest without inventing a purchasable product.
  return [{ productId: "demo-unavailable" }];
}

export default async function CommerceProductPage({ params }: { params: Promise<{ productId: string }> }) {
  const { productId } = await params;
  return <CommerceProductDetail productId={productId} />;
}
