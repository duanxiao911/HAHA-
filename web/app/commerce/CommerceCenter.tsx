"use client";

import { FormEvent, useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ConfirmDialog } from "@/components/community/ConfirmDialog";
import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import {
  AUTH_REQUIRED,
  cancelCommerceOrder,
  checkoutCommerceCart,
  CommerceOrder,
  CommerceSnapshot,
  confirmCommerceDelivery,
  createCommerceProduct,
  decideCommerceAfterSale,
  getAuthSessionSnapshot,
  getCommerceCenter,
  getServerAuthSessionSnapshot,
  initializeAuthSession,
  openCommerceStore,
  payCommerceSandboxOrder,
  removeCommerceCartItem,
  requestCommerceAfterSale,
  reviewCommerceProduct,
  shipCommerceOrder,
  submitCommerceProduct,
  subscribeAuthSession,
  updateCommerceCart,
  updateCommerceInventory,
} from "@/lib/api";

type View = "market" | "cart" | "orders" | "seller" | "review";
type Confirmation = { title: string; description: string; label: string; tone?: "danger" | "primary"; action: () => Promise<CommerceSnapshot> };
const views = new Set<View>(["market", "cart", "orders", "seller", "review"]);
const money = new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY" });
const statusLabels: Record<string, string> = {
  draft: "草稿", submitted: "待审核", approved: "已审核待上架", rejected: "已退回", listed: "沙盒在售", delisted: "已下架",
  awaiting_sandbox_payment: "待沙盒支付", paid: "沙盒已支付", shipped: "沙盒已发货", completed: "已完成",
  after_sales: "售后中", cancelled: "已取消", requested: "待处理", resolved: "已解决",
};
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : "操作失败，请刷新后重试。";

export function CommerceCenter() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const authState = useSyncExternalStore(subscribeAuthSession, getAuthSessionSnapshot, getServerAuthSessionSnapshot);
  const canLoad = !AUTH_REQUIRED || authState === "authenticated";
  const requested = searchParams.get("view") as View | null;
  const view = requested && views.has(requested) ? requested : "market";
  const [snapshot, setSnapshot] = useState<CommerceSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [storeName, setStoreName] = useState("");
  const [product, setProduct] = useState({ title: "", summary: "", price: "", source: "" });

  useEffect(() => { void initializeAuthSession(); }, []);
  const load = useCallback(async () => {
    if (!canLoad) return;
    setError("");
    try { setSnapshot(await getCommerceCenter()); }
    catch (cause) { setError(errorText(cause)); }
  }, [canLoad]);
  useEffect(() => {
    if (!canLoad) return;
    let active = true;
    void getCommerceCenter()
      .then((value) => { if (active) setSnapshot(value); })
      .catch((cause: unknown) => { if (active) setError(errorText(cause)); });
    return () => { active = false; };
  }, [canLoad]);

  function selectView(next: View) {
    const params = new URLSearchParams(searchParams.toString());
    if (next === "market") params.delete("view"); else params.set("view", next);
    router.push(`/commerce${params.size ? `?${params.toString()}` : ""}`, { scroll: false });
  }

  async function run(action: () => Promise<CommerceSnapshot>, message: string): Promise<boolean> {
    setBusy(true); setError(""); setFeedback("");
    try { setSnapshot(await action()); setFeedback(message); return true; }
    catch (cause) { setError(errorText(cause)); return false; }
    finally { setBusy(false); }
  }

  async function createStore(event: FormEvent) {
    event.preventDefault();
    if (await run(() => openCommerceStore(storeName), "内部测试店铺已创建。")) setStoreName("");
  }

  async function createProduct(event: FormEvent) {
    event.preventDefault();
    const priceCents = Math.round(Number(product.price) * 100);
    if (!Number.isFinite(priceCents) || priceCents < 1) { setError("请输入有效的沙盒价格。"); return; }
    if (await run(() => createCommerceProduct({ title: product.title, summary: product.summary, price_cents: priceCents, source_note: product.source }), "商品草稿已保存。")) setProduct({ title: "", summary: "", price: "", source: "" });
  }

  if (AUTH_REQUIRED && authState === "unknown") return <ProductFrame><StateNotice kind="loading" title="正在验证安全会话" description="交易状态只向当前账户开放。" /></ProductFrame>;
  if (AUTH_REQUIRED && authState === "anonymous") return <ProductFrame><StateNotice kind="forbidden" title="请先登录文化账户" description="交易沙盒需要有效账户会话。" actionLabel="前往登录" actionHref="/login" /></ProductFrame>;
  if (!snapshot) return <ProductFrame>{error ? <StateNotice kind="error" title="交易沙盒暂不可用" description={error} actionLabel="重试" onAction={() => void load()} /> : <StateNotice kind="loading" title="正在读取交易状态" description="从服务端读取商品、购物车与订单。" />}</ProductFrame>;

  const isSeller = snapshot.roles.includes("seller");
  const canReview = snapshot.roles.includes("reviewer") || snapshot.roles.includes("admin");
  const nav: [View, string][] = [
    ["market", "商品"], ["cart", `购物车 ${snapshot.cart.length}`], ["orders", `我的订单 ${snapshot.buyer_orders.length}`],
    ...(isSeller ? [["seller", "卖家工作台"] as [View, string]] : []),
    ...(canReview ? [["review", `商品审核 ${snapshot.review_queue.length}`] as [View, string]] : []),
  ];

  return <ProductFrame className="commerceFrame" mainClassName="commercePage" demoLabel="Gate D · INTERNAL SANDBOX">
    <section className="commerceHero">
      <div><small>HAHA HERITAGE COMMERCE</small><h1>非遗交易沙盒</h1><p>商品审核、库存、订单、支付状态、履约与售后均由服务端持久化；常用操作按购买流程排列。</p></div>
      <div className="commerceSandboxBadge"><b>INTERNAL SANDBOX</b><span>不处理真实资金</span></div>
    </section>
    <div className="commerceBoundary" role="note"><strong>边界说明</strong><span>{snapshot.sandbox.notice} 当前仅支持单店结算。</span></div>
    <nav className="commerceNav" aria-label="交易沙盒视图">{nav.map(([key, label]) => <button type="button" className={view === key ? "active" : ""} aria-current={view === key ? "page" : undefined} onClick={() => selectView(key)} key={key}>{label}</button>)}</nav>
    {error ? <div className="commerceAlert" role="alert">{error}</div> : null}
    {feedback ? <div className="productToast" role="status">{feedback}</div> : null}

    {view === "market" ? <section className="commerceSection">
      <header><div><small>REVIEWED TEST LISTINGS</small><h2>沙盒商品</h2><p>这里只展示已审核且有库存的内部测试商品；来源说明仍需独立判断。</p></div><button className="productButtonSecondary" type="button" onClick={() => selectView("cart")}>查看购物车</button></header>
      {snapshot.catalog.length ? <div className="commerceProductGrid">{snapshot.catalog.map((item) => <article key={item.id}>
        <span className="productStatusPill is-good">{statusLabels[item.status]}</span><h3>{item.title}</h3><p>{item.summary}</p>
        <dl><div><dt>沙盒价格</dt><dd>{money.format(item.price_cents / 100)}</dd></div><div><dt>可用库存</dt><dd>{item.inventory.available_qty}</dd></div></dl>
        <details><summary>查看来源与审核边界</summary><p>{item.source_note}</p><small>{item.provenance === "seller_supplied_unverified" ? "卖家自述，非权威认证" : item.provenance}</small></details>
        <button className="productButton" type="button" disabled={busy} onClick={() => void run(() => updateCommerceCart(item.id, 1, snapshot.cart.find((line) => line.product_id === item.id)?.version ?? 0), "已加入购物车。")}>{snapshot.cart.some((line) => line.product_id === item.id) ? "购物车已有 1 件" : "加入购物车"}</button>
      </article>)}</div> : <StateNotice kind="empty" title="还没有可购买的沙盒商品" description="卖家商品通过独立审核并设置库存后才会出现在这里。" />}
    </section> : null}

    {view === "cart" ? <section className="commerceSection">
      <header><div><small>SINGLE-STORE CHECKOUT</small><h2>购物车</h2><p>结算时会在同一事务内校验库存并创建订单。</p></div></header>
      {snapshot.cart.length ? <><ul className="commerceList">{snapshot.cart.map((line) => <li key={line.id}><div><span>数量 {line.quantity}</span><h3>{line.product?.title ?? "商品已不可用"}</h3><p>{line.product ? money.format(line.product.price_cents / 100) : "请移除"}</p></div><button className="productButtonQuiet" type="button" disabled={busy} onClick={() => void run(() => removeCommerceCartItem(line.product_id), "已从购物车移除。")}>移除</button></li>)}</ul><div className="commercePrimaryAction"><span>只支持单店商品一起结算</span><button className="productButton" type="button" disabled={busy} onClick={() => setConfirmation({ title: "创建内部沙盒订单？", description: "系统将锁定当前库存并创建待沙盒支付订单，不会扣取真实资金。", label: "确认结算", tone: "primary", action: checkoutCommerceCart })}>结算</button></div></> : <StateNotice kind="empty" title="购物车是空的" description="从沙盒商品页加入商品后再结算。" actionLabel="浏览商品" onAction={() => selectView("market")} />}
    </section> : null}

    {view === "orders" ? <section className="commerceSection">
      <header><div><small>BUYER ORDERS</small><h2>我的订单</h2><p>支付、履约与售后均为内部状态演练。</p></div></header>
      {snapshot.buyer_orders.length ? <ul className="commerceOrderList">{snapshot.buyer_orders.map((order) => <OrderCard order={order} key={order.id} actions={<>
        {order.status === "awaiting_sandbox_payment" ? <><button className="productButton" type="button" disabled={busy} onClick={() => setConfirmation({ title: "确认执行沙盒支付？", description: "不会扣取真实资金，也不会要求输入银行卡或支付凭证。", label: "确认沙盒支付", tone: "primary", action: () => payCommerceSandboxOrder(order.id, order.version) })}>沙盒支付</button><button className="productButtonQuiet identityDangerAction" type="button" disabled={busy} onClick={() => setConfirmation({ title: "取消这笔订单？", description: "订单将取消并把占用库存退回。", label: "取消订单", action: () => cancelCommerceOrder(order.id, order.version) })}>取消订单</button></> : null}
        {order.status === "shipped" ? <button className="productButton" type="button" disabled={busy} onClick={() => void run(() => confirmCommerceDelivery(order.id, order.version), "已确认沙盒收货。")}>确认收货</button> : null}
        {["paid", "shipped", "completed"].includes(order.status) ? <button className="productButtonSecondary" type="button" disabled={busy} onClick={() => setConfirmation({ title: "发起内部售后？", description: "只会创建可审计售后状态，不触发真实退款。", label: "提交售后", tone: "primary", action: () => requestCommerceAfterSale(order.id, order.version, "内部沙盒售后验证，不触发真实退款。") })}>申请售后</button> : null}
      </>} />)}</ul> : <StateNotice kind="empty" title="还没有订单" description="从购物车结算后，订单会保存在当前账户。" actionLabel="浏览商品" onAction={() => selectView("market")} />}
      {snapshot.buyer_after_sales.length ? <div className="commerceSubsection"><h3>售后记录</h3>{snapshot.buyer_after_sales.map((item) => <p key={item.id}><b>{statusLabels[item.status] ?? item.status}</b> · {item.reason}{item.decision_note ? ` · ${item.decision_note}` : ""}</p>)}</div> : null}
    </section> : null}

    {view === "seller" && isSeller ? <section className="commerceSection">
      <header><div><small>SELLER WORKSPACE</small><h2>卖家工作台</h2><p>店铺、商品与库存归属当前已授权卖家账户。</p></div></header>
      {!snapshot.store ? <form className="commerceForm" onSubmit={createStore}><label htmlFor="store-name">店铺名称<input id="store-name" value={storeName} onChange={(event) => setStoreName(event.target.value)} required maxLength={200} /></label><button className="productButton" disabled={busy}>创建内部测试店铺</button></form> : <>
        <div className="commerceStoreLine"><span>当前店铺</span><strong>{snapshot.store.name}</strong><small>内部测试 · {snapshot.store.status}</small></div>
        <form className="commerceForm commerceProductForm" onSubmit={createProduct}>
          <label htmlFor="product-title">商品名称<input id="product-title" value={product.title} onChange={(event) => setProduct({ ...product, title: event.target.value })} required /></label>
          <label htmlFor="product-price">沙盒价格（元）<input id="product-price" type="number" min="0.01" step="0.01" value={product.price} onChange={(event) => setProduct({ ...product, price: event.target.value })} required /></label>
          <label className="wide" htmlFor="product-summary">商品说明<textarea id="product-summary" value={product.summary} onChange={(event) => setProduct({ ...product, summary: event.target.value })} required /></label>
          <label className="wide" htmlFor="product-source">来源与授权说明<textarea id="product-source" value={product.source} onChange={(event) => setProduct({ ...product, source: event.target.value })} placeholder="必须如实说明来源、授权范围与待核验事项" required /></label>
          <button className="productButton wide" disabled={busy}>保存商品草稿</button>
        </form>
      </>}
      {snapshot.seller_products.length ? <ul className="commerceList">{snapshot.seller_products.map((item) => <li key={item.id}><div><span>{statusLabels[item.status] ?? item.status} · v{item.version}</span><h3>{item.title}</h3><p>{item.reviewer_note || item.source_note}</p></div><div className="commerceRowActions">{["draft", "rejected"].includes(item.status) ? <button className="productButton" type="button" disabled={busy} onClick={() => void run(() => submitCommerceProduct(item.id, item.version), "商品已提交审核。")}>提交审核</button> : null}{["approved", "delisted"].includes(item.status) ? <button className="productButtonSecondary" type="button" disabled={busy} onClick={() => void run(() => updateCommerceInventory(item.id, 5, item.inventory.version), item.status === "delisted" ? "商品已重新上架。" : "商品已设置库存并上架。")}>{item.status === "delisted" ? "重新上架 5 件" : "设置库存 5 件"}</button> : null}{item.status === "listed" ? <button className="productButtonQuiet identityDangerAction" type="button" disabled={busy} onClick={() => setConfirmation({ title: "下架这个商品？", description: "商品会立即从买家目录移除，可用库存归零；历史订单和审计记录会保留。", label: "确认下架", tone: "danger", action: () => updateCommerceInventory(item.id, 0, item.inventory.version) })}>下架商品</button> : null}</div></li>)}</ul> : null}
      {snapshot.seller_orders.length ? <div className="commerceSubsection"><h3>待履约订单</h3>{snapshot.seller_orders.map((order) => <OrderCard order={order} key={order.id} actions={order.status === "paid" ? <button className="productButton" type="button" disabled={busy} onClick={() => void run(() => shipCommerceOrder(order.id, order.version, "内部沙盒履约记录，无真实物流单号。"), "订单已标记为沙盒发货。")}>标记沙盒发货</button> : null} />)}</div> : null}
      {snapshot.seller_after_sales.some((item) => item.status === "requested") ? <div className="commerceSubsection"><h3>待处理售后</h3>{snapshot.seller_after_sales.filter((item) => item.status === "requested").map((item) => <div className="commerceDecision" key={item.id}><p>{item.reason}</p><button className="productButton" type="button" disabled={busy} onClick={() => void run(() => decideCommerceAfterSale(item.id, item.version, "approved", "内部沙盒售后已受理，不代表真实退款完成。"), "售后已受理。")}>受理</button><button className="productButtonSecondary" type="button" disabled={busy} onClick={() => void run(() => decideCommerceAfterSale(item.id, item.version, "rejected", "内部沙盒售后未通过。"), "售后已驳回。")}>驳回</button></div>)}</div> : null}
    </section> : null}

    {view === "review" && canReview ? <section className="commerceSection">
      <header><div><small>INDEPENDENT PRODUCT REVIEW</small><h2>商品审核</h2><p>审核员不能审核自己的商品；通过仅表示可进入内部交易沙盒。</p></div></header>
      {snapshot.review_queue.length ? <ul className="commerceList">{snapshot.review_queue.map((item) => <li key={item.id}><div><span>卖家 {item.seller_user_id} · v{item.version}</span><h3>{item.title}</h3><p>{item.summary}</p><small>来源说明：{item.source_note}</small></div><div className="commerceRowActions"><button className="productButton" type="button" disabled={busy} onClick={() => setConfirmation({ title: "批准进入内部交易沙盒？", description: "仅批准状态流转，不构成非遗事实、知识产权或商品资质认证。", label: "审核通过", tone: "primary", action: () => reviewCommerceProduct(item.id, "approved", "仅批准进入内部交易沙盒；正式来源与资质仍需线下核验。", item.version) })}>审核通过</button><button className="productButtonSecondary" type="button" disabled={busy} onClick={() => void run(() => reviewCommerceProduct(item.id, "rejected", "资料不足，请补充来源与授权说明。", item.version), "商品已退回卖家。")}>退回补充</button></div></li>)}</ul> : <StateNotice kind="empty" title="没有待审核商品" description="卖家提交商品后会出现在这里。" />}
    </section> : null}

    <ConfirmDialog open={Boolean(confirmation)} title={confirmation?.title ?? ""} description={confirmation?.description ?? ""} confirmLabel={confirmation?.label ?? "确认"} tone={confirmation?.tone} busy={busy} onCancel={() => setConfirmation(null)} onConfirm={() => { if (!confirmation) return; void run(confirmation.action, `${confirmation.label}已完成。`).then((success) => { if (success) setConfirmation(null); }); }} />
  </ProductFrame>;
}

function OrderCard({ order, actions }: { order: CommerceOrder; actions: React.ReactNode }) {
  return <li><div><span className="productStatusPill is-warning">{statusLabels[order.status] ?? order.status}</span><h3>{order.items.map((item) => item.title_snapshot).join("、")}</h3><p>{money.format(order.total_cents / 100)} · 订单 {order.id.slice(-8)}</p>{order.payment ? <small>支付渠道：内部沙盒 · 不涉及真实资金</small> : null}{order.fulfillment ? <small>履约：{order.fulfillment.tracking_note}</small> : null}</div><div className="commerceRowActions">{actions}</div></li>;
}
