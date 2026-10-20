"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import {
  AUTH_REQUIRED,
  CommerceProduct,
  getAuthSessionSnapshot,
  getCommerceProduct,
  getServerAuthSessionSnapshot,
  initializeAuthSession,
  subscribeAuthSession,
} from "@/lib/api";

const money = new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY" });
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : "商品暂时无法读取，请稍后重试。";

export function CommerceProductDetail({ productId }: { productId: string }) {
  const authState = useSyncExternalStore(subscribeAuthSession, getAuthSessionSnapshot, getServerAuthSessionSnapshot);
  const canLoad = !AUTH_REQUIRED || authState === "authenticated";
  const [product, setProduct] = useState<CommerceProduct | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!canLoad) return;
    setError("");
    try { setProduct(await getCommerceProduct(productId)); }
    catch (cause) { setError(errorText(cause)); }
  }, [canLoad, productId]);

  useEffect(() => { void initializeAuthSession(); }, []);
  useEffect(() => {
    if (!canLoad) return;
    let active = true;
    void getCommerceProduct(productId)
      .then((value) => { if (active) setProduct(value); })
      .catch((cause: unknown) => { if (active) setError(errorText(cause)); });
    return () => { active = false; };
  }, [canLoad, productId]);

  if (AUTH_REQUIRED && authState === "unknown") return <ProductFrame><StateNotice kind="loading" title="正在验证安全会话" description="商品详情只向当前文化账户开放。" /></ProductFrame>;
  if (AUTH_REQUIRED && authState === "anonymous") return <ProductFrame><StateNotice kind="forbidden" title="请先登录文化账户" description="登录后可查看商品并保存购物状态。" actionLabel="前往登录" actionHref="/login" /></ProductFrame>;
  if (!product) return <ProductFrame mainClassName="commercePage">{error ? <StateNotice kind="error" title="商品暂不可用" description={error} actionLabel="重试" onAction={() => void load()} /> : <StateNotice kind="loading" title="正在读取商品详情" description="从服务端读取商品、库存与可信信息。" />}</ProductFrame>;

  return <ProductFrame className="commerceFrame" mainClassName="commercePage" demoLabel="INTERNAL COMMERCE PREVIEW">
    <Link className="commerceBackLink" href="/commerce">← 返回逛好物</Link>
    <section className="commerceSection commerceDetailGrid">
      <div className="commerceDetailMedia">{product.category?.name ?? "HAHA HERITAGE GOODS"}</div>
      <div className="commerceDetailCopy">
        <span className="productStatusPill is-good">{product.category?.name ?? "非遗好物"}</span>
        <h1>{product.title}</h1>
        <p>{product.summary}</p>
        <div className="commerceDetailPrice">{money.format(product.price_cents / 100)}</div>
        <dl className="commerceFacts">
          <div><dt>工艺类型</dt><dd>{product.craft_type || "商家暂未填写"}</dd></div>
          <div><dt>来源地区</dt><dd>{product.origin_region || "商家暂未填写"}</dd></div>
          <div><dt>季节主题</dt><dd>{product.season_tag || "常规好物"}</dd></div>
          <div><dt>沙盒库存</dt><dd>{product.inventory.available_qty}</dd></div>
        </dl>
        <div className="commerceTrustBox" role="note">
          <h2>{product.trust?.label ?? "商家提供，待独立核验"}</h2>
          <p>{product.source_note}</p>
          <p>平台审核仅用于内部商品状态流转，不构成非遗认定、质量背书或知识产权认证。</p>
        </div>
        <Link className="productButton" href="/commerce?view=market">返回目录选购</Link>
      </div>
    </section>
  </ProductFrame>;
}
