"use client";

import { FormEvent, useCallback, useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { ConfirmDialog } from "@/components/community/ConfirmDialog";
import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import {
  AUTH_REQUIRED,
  cancelCommerceOrder,
  checkoutCommerceCart,
  CommerceOrder,
  CommerceCatalog,
  CommerceProduct,
  CommerceSnapshot,
  confirmCommerceDelivery,
  createCommerceProduct,
  decideCommerceAfterSale,
  getAuthSessionSnapshot,
  getCommerceCenter,
  getCommerceCatalog,
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
const afterSaleStatusLabels: Record<string, string> = {
  requested: "待处理", approved: "已受理", rejected: "已驳回", resolved: "已解决",
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
  const [product, setProduct] = useState({ title: "", summary: "", price: "", source: "", category: "other", craft: "", region: "", season: "" });
  const [catalogQuery, setCatalogQuery] = useState("");
  const [catalogCategory, setCatalogCategory] = useState("");
  const [catalog, setCatalog] = useState<CommerceCatalog | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [cartQuantities, setCartQuantities] = useState<Record<string, string>>({});
  const [inventoryQuantities, setInventoryQuantities] = useState<Record<string, string>>({});

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
  useEffect(() => {
    if (!canLoad || view !== "market") return;
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams();
      if (catalogQuery.trim()) params.set("q", catalogQuery.trim());
      if (catalogCategory) params.set("category", catalogCategory);
      setCatalogLoading(true);
      void getCommerceCatalog(params)
        .then(setCatalog)
        .catch((cause: unknown) => setError(errorText(cause)))
        .finally(() => setCatalogLoading(false));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [canLoad, catalogCategory, catalogQuery, view]);

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
    if (await run(() => createCommerceProduct({ title: product.title, summary: product.summary, price_cents: priceCents, source_note: product.source, category_slug: product.category, craft_type: product.craft, origin_region: product.region, season_tag: product.season }), "商品草稿已保存。")) setProduct({ title: "", summary: "", price: "", source: "", category: "other", craft: "", region: "", season: "" });
  }

  function saveCartQuantity(item: CommerceProduct, fallback: number, version: number) {
    const quantity = Number(cartQuantities[item.id] ?? fallback);
    if (!Number.isInteger(quantity) || quantity < 1 || quantity > Math.min(99, item.inventory.available_qty)) {
      setError(`请输入 1 至 ${Math.min(99, item.inventory.available_qty)} 的整数数量。`);
      return;
    }
    void run(() => updateCommerceCart(item.id, quantity, version), "购物车数量已更新。");
  }

  function saveInventory(item: CommerceProduct) {
    const quantity = Number(inventoryQuantities[item.id] ?? String(item.inventory.available_qty || 1));
    if (!Number.isInteger(quantity) || quantity < 1 || quantity > 1_000_000) {
      setError("请输入 1 至 1000000 的整数库存。");
      return;
    }
    void run(
      () => updateCommerceInventory(item.id, quantity, item.inventory.version),
      item.status === "delisted" ? "商品已重新上架。" : "商品库存已更新并上架。",
    );
  }

  if (AUTH_REQUIRED && authState === "unknown") return <ProductFrame><StateNotice kind="loading" title="正在验证安全会话" description="交易状态只向当前账户开放。" /></ProductFrame>;
  if (AUTH_REQUIRED && authState === "anonymous") return <ProductFrame><StateNotice kind="forbidden" title="请先登录文化账户" description="交易沙盒需要有效账户会话。" actionLabel="前往登录" actionHref="/login" /></ProductFrame>;
  if (!snapshot) return <ProductFrame>{error ? <StateNotice kind="error" title="交易沙盒暂不可用" description={error} actionLabel="重试" onAction={() => void load()} /> : <StateNotice kind="loading" title="正在读取交易状态" description="从服务端读取商品、购物车与订单。" />}</ProductFrame>;

  const isSeller = snapshot.roles.includes("seller");
  const canReview = snapshot.roles.includes("reviewer") || snapshot.roles.includes("admin");
  const filteredCatalog = catalog?.items ?? snapshot.catalog;
  const nav: [View, string][] = [
    ["market", "商品"], ["cart", `购物车 ${snapshot.cart.length}`], ["orders", `我的订单 ${snapshot.buyer_orders.length}`],
    ...(isSeller ? [["seller", "卖家工作台"] as [View, string]] : []),
    ...(canReview ? [["review", `商品审核 ${snapshot.review_queue.length}`] as [View, string]] : []),
  ];

  return <ProductFrame className="commerceFrame" mainClassName="commercePage" demoLabel="INTERNAL COMMERCE PREVIEW">
    <section className="commerceHero">
      <div><small>HAHA HERITAGE MARKET</small><h1>发现值得带回家的非遗好物</h1><p>按工艺与地区探索，由服务端保存购物状态。商品文化关联与来源信息分级展示，不把商家自述包装成权威认证。</p><div className="commerceHeroActions"><a className="productButton" href="#commerce-catalog">开始逛好物</a><Link className="productButtonSecondary" href="/commerce/advisor">问 AI 智能导购</Link></div></div>
      <div className="commerceSandboxBadge"><b>INTERNAL SANDBOX</b><span>不处理真实资金</span></div>
    </section>
    <div className="commerceBoundary" role="note"><strong>边界说明</strong><span>{snapshot.sandbox.notice} 当前仅支持单店结算。</span></div>
    <nav className="commerceNav" aria-label="交易沙盒视图">{nav.map(([key, label]) => <button type="button" className={view === key ? "active" : ""} aria-current={view === key ? "page" : undefined} onClick={() => selectView(key)} key={key}>{label}</button>)}</nav>
    {error ? <div className="commerceAlert" role="alert">{error}</div> : null}
    {feedback ? <div className="productToast" role="status">{feedback}</div> : null}

    {view === "market" ? <section className="commerceSection" id="commerce-catalog">
      <header><div><small>CURATED DISCOVERY</small><h2>逛非遗好物</h2><p>从自然语言搜索或常见工艺分类开始；当前只展示已审核且有库存的内部测试商品。</p></div><button className="productButtonSecondary" type="button" onClick={() => selectView("cart")}>查看购物车</button></header>
      <div className="commerceCategoryRail" aria-label="商品分类"><button type="button" className={!catalogCategory ? "active" : ""} onClick={() => setCatalogCategory("")}>全部</button>{snapshot.categories.map((item) => <button type="button" className={catalogCategory === item.slug ? "active" : ""} onClick={() => setCatalogCategory(item.slug)} key={item.id}>{item.name}</button>)}</div>
      <div className="commerceToolbar"><label htmlFor="commerce-search">搜索商品<input id="commerce-search" type="search" value={catalogQuery} onChange={(event) => setCatalogQuery(event.target.value)} placeholder="例如：送长辈的陶瓷茶具" /></label><span>{catalogLoading ? "正在搜索…" : `找到 ${catalog?.total ?? snapshot.catalog.length} 件`}</span></div>
      {filteredCatalog.length ? <div className="commerceProductGrid">{filteredCatalog.map((item) => {
        const cartLine = snapshot.cart.find((line) => line.product_id === item.id);
        return <article key={item.id}>
        <div className="commerceProductVisual" aria-hidden="true"><span>{item.category?.name ?? "非遗好物"}</span></div><span className="productStatusPill is-good">{item.category?.name ?? statusLabels[item.status]}</span><h3><Link href={`/commerce/products/${encodeURIComponent(item.id)}`}>{item.title}</Link></h3><p>{item.summary}</p>
        <dl><div><dt>沙盒价格</dt><dd>{money.format(item.price_cents / 100)}</dd></div><div><dt>可用库存</dt><dd>{item.inventory.available_qty}</dd></div></dl>
        <details><summary>查看来源与可信边界</summary><p>{item.source_note}</p><small>{item.trust?.label ?? (item.provenance === "seller_supplied_unverified" ? "商家提供，待独立核验" : item.provenance)}</small></details>
        <div className="commerceQuantity"><label htmlFor={`catalog-quantity-${item.id}`}>数量<input id={`catalog-quantity-${item.id}`} type="number" min="1" max={Math.min(99, item.inventory.available_qty)} step="1" value={cartQuantities[item.id] ?? String(cartLine?.quantity ?? 1)} onChange={(event) => setCartQuantities({ ...cartQuantities, [item.id]: event.target.value })} /></label><button className="productButton" type="button" disabled={busy} onClick={() => saveCartQuantity(item, cartLine?.quantity ?? 1, cartLine?.version ?? 0)}>{cartLine ? "更新购物车" : "加入购物车"}</button></div>
      </article>})}</div> : catalogLoading ? <StateNotice kind="loading" title="正在寻找合适的商品" description="从服务端目录读取结果。" /> : (catalogQuery || catalogCategory) ? <StateNotice kind="empty" title="没有找到匹配商品" description="换一个说法或分类再试试。" actionLabel="清除筛选" onAction={() => { setCatalogQuery(""); setCatalogCategory(""); }} /> : <StateNotice kind="empty" title="还没有可购买商品" description="卖家商品通过独立审核并设置库存后才会出现在这里。" />}
    </section> : null}

    {view === "cart" ? <section className="commerceSection">
      <header><div><small>SINGLE-STORE CHECKOUT</small><h2>购物车</h2><p>结算时会在同一事务内校验库存并创建订单。</p></div></header>
      {snapshot.cart.length ? <><ul className="commerceList">{snapshot.cart.map((line) => <li key={line.id}><div><span>数量 {line.quantity}</span><h3>{line.product?.title ?? "商品已不可用"}</h3><p>{line.product ? `${money.format(line.product.price_cents / 100)} · 小计 ${money.format(line.product.price_cents * line.quantity / 100)}` : "请移除"}</p></div><div className="commerceRowActions">{line.product ? <div className="commerceQuantity compact"><label htmlFor={`cart-quantity-${line.id}`}>数量<input id={`cart-quantity-${line.id}`} type="number" min="1" max={Math.min(99, line.product.inventory.available_qty)} step="1" value={cartQuantities[line.product_id] ?? String(line.quantity)} onChange={(event) => setCartQuantities({ ...cartQuantities, [line.product_id]: event.target.value })} /></label><button className="productButtonSecondary" type="button" disabled={busy} onClick={() => saveCartQuantity(line.product!, line.quantity, line.version)}>更新</button></div> : null}<button className="productButtonQuiet" type="button" disabled={busy} onClick={() => void run(() => removeCommerceCartItem(line.product_id), "已从购物车移除。")}>移除</button></div></li>)}</ul><div className="commercePrimaryAction"><span>只支持单店商品一起结算</span><button className="productButton" type="button" disabled={busy} onClick={() => setConfirmation({ title: "创建内部沙盒订单？", description: "系统将锁定当前库存并创建待沙盒支付订单，不会扣取真实资金。", label: "确认结算", tone: "primary", action: checkoutCommerceCart })}>结算</button></div></> : <StateNotice kind="empty" title="购物车是空的" description="从沙盒商品页加入商品后再结算。" actionLabel="浏览商品" onAction={() => selectView("market")} />}
    </section> : null}

    {view === "orders" ? <section className="commerceSection">
      <header><div><small>BUYER ORDERS</small><h2>我的订单</h2><p>支付、履约与售后均为内部状态演练。</p></div></header>
      {snapshot.buyer_orders.length ? <ul className="commerceOrderList">{snapshot.buyer_orders.map((order) => <OrderCard order={order} key={order.id} actions={<>
        {order.status === "awaiting_sandbox_payment" ? <><button className="productButton" type="button" disabled={busy} onClick={() => setConfirmation({ title: "确认执行沙盒支付？", description: "不会扣取真实资金，也不会要求输入银行卡或支付凭证。", label: "确认沙盒支付", tone: "primary", action: () => payCommerceSandboxOrder(order.id, order.version) })}>沙盒支付</button><button className="productButtonQuiet identityDangerAction" type="button" disabled={busy} onClick={() => setConfirmation({ title: "取消这笔订单？", description: "订单将取消并把占用库存退回。", label: "取消订单", action: () => cancelCommerceOrder(order.id, order.version) })}>取消订单</button></> : null}
        {order.status === "shipped" ? <button className="productButton" type="button" disabled={busy} onClick={() => setConfirmation({ title: "确认已经收到沙盒商品？", description: "确认后订单会进入已完成状态；如有问题，请先申请内部售后。", label: "确认已收货", tone: "primary", action: () => confirmCommerceDelivery(order.id, order.version) })}>确认收货</button> : null}
        {["paid", "shipped", "completed"].includes(order.status) ? <button className="productButtonSecondary" type="button" disabled={busy} onClick={() => setConfirmation({ title: "发起内部售后？", description: "只会创建可审计售后状态，不触发真实退款。", label: "提交售后", tone: "primary", action: () => requestCommerceAfterSale(order.id, order.version, "内部沙盒售后验证，不触发真实退款。") })}>申请售后</button> : null}
      </>} />)}</ul> : <StateNotice kind="empty" title="还没有订单" description="从购物车结算后，订单会保存在当前账户。" actionLabel="浏览商品" onAction={() => selectView("market")} />}
      {snapshot.buyer_after_sales.length ? <div className="commerceSubsection"><h3>售后记录</h3>{snapshot.buyer_after_sales.map((item) => <p key={item.id}><b>{afterSaleStatusLabels[item.status] ?? item.status}</b> · {item.reason}{item.decision_note ? ` · ${item.decision_note}` : ""}</p>)}</div> : null}
    </section> : null}

    {view === "seller" && isSeller ? <section className="commerceSection">
      <header><div><small>SELLER WORKSPACE</small><h2>卖家工作台</h2><p>店铺、商品与库存归属当前已授权卖家账户。</p></div></header>
      <div className="commerceSellerMetrics" aria-label="店铺经营概览">
        <div><span>全部商品</span><strong>{snapshot.seller_products.length}</strong><small>当前店铺</small></div>
        <div><span>待审核</span><strong>{snapshot.seller_products.filter((item) => item.status === "submitted").length}</strong><small>由独立审核员处理</small></div>
        <div><span>沙盒在售</span><strong>{snapshot.seller_products.filter((item) => item.status === "listed").length}</strong><small>库存大于零</small></div>
        <div><span>待履约</span><strong>{snapshot.seller_orders.filter((item) => item.status === "paid").length}</strong><small>仅内部状态演练</small></div>
      </div>
      <ol className="commerceSellerSteps"><li>保存结构化商品草稿</li><li>提交独立审核</li><li>审核通过后设置库存</li><li>处理订单与售后</li></ol>
      {!snapshot.store ? <form className="commerceForm" onSubmit={createStore}><label htmlFor="store-name">店铺名称<input id="store-name" value={storeName} onChange={(event) => setStoreName(event.target.value)} required maxLength={200} /></label><button className="productButton" disabled={busy}>创建内部测试店铺</button></form> : <>
        <div className="commerceStoreLine"><span>当前店铺</span><strong>{snapshot.store.name}</strong><small>内部测试 · {snapshot.store.status}</small></div>
        <form className="commerceForm commerceProductForm" onSubmit={createProduct}>
          <label htmlFor="product-title">商品名称<input id="product-title" value={product.title} onChange={(event) => setProduct({ ...product, title: event.target.value })} required /></label>
          <label htmlFor="product-price">沙盒价格（元）<input id="product-price" type="number" min="0.01" step="0.01" value={product.price} onChange={(event) => setProduct({ ...product, price: event.target.value })} required /></label>
          <label htmlFor="product-category">商品分类<select id="product-category" value={product.category} onChange={(event) => setProduct({ ...product, category: event.target.value })}>{snapshot.categories.map((item) => <option value={item.slug} key={item.id}>{item.name}</option>)}</select></label>
          <label htmlFor="product-craft">工艺类型<input id="product-craft" value={product.craft} onChange={(event) => setProduct({ ...product, craft: event.target.value })} placeholder="如：手工拉坯" maxLength={120} /></label>
          <label htmlFor="product-region">来源地区<input id="product-region" value={product.region} onChange={(event) => setProduct({ ...product, region: event.target.value })} placeholder="如：江西景德镇" maxLength={120} /></label>
          <label htmlFor="product-season">季节主题<input id="product-season" value={product.season} onChange={(event) => setProduct({ ...product, season: event.target.value })} placeholder="如：春日上新" maxLength={80} /></label>
          <label className="wide" htmlFor="product-summary">商品说明<textarea id="product-summary" value={product.summary} onChange={(event) => setProduct({ ...product, summary: event.target.value })} required /></label>
          <label className="wide" htmlFor="product-source">来源与授权说明<textarea id="product-source" value={product.source} onChange={(event) => setProduct({ ...product, source: event.target.value })} placeholder="必须如实说明来源、授权范围与待核验事项；不得把商家自述写成权威认证" required /></label>
          <button className="productButton wide" disabled={busy}>保存商品草稿</button>
        </form>
      </>}
      {snapshot.seller_products.length ? <ul className="commerceList">{snapshot.seller_products.map((item) => <li key={item.id}><div><span>{statusLabels[item.status] ?? item.status} · v{item.version}</span><h3>{item.title}</h3><p>{item.reviewer_note || item.source_note}</p></div><div className="commerceRowActions">{["draft", "rejected"].includes(item.status) ? <button className="productButton" type="button" disabled={busy} onClick={() => void run(() => submitCommerceProduct(item.id, item.version), "商品已提交审核。")}>提交审核</button> : null}{["approved", "delisted"].includes(item.status) ? <div className="commerceQuantity compact"><label htmlFor={`inventory-${item.id}`}>上架库存<input id={`inventory-${item.id}`} type="number" min="1" max="1000000" step="1" value={inventoryQuantities[item.id] ?? String(item.inventory.available_qty || 1)} onChange={(event) => setInventoryQuantities({ ...inventoryQuantities, [item.id]: event.target.value })} /></label><button className="productButtonSecondary" type="button" disabled={busy} onClick={() => saveInventory(item)}>{item.status === "delisted" ? "重新上架" : "设置库存并上架"}</button></div> : null}{item.status === "listed" ? <button className="productButtonQuiet identityDangerAction" type="button" disabled={busy} onClick={() => setConfirmation({ title: "下架这个商品？", description: "商品会立即从买家目录移除，可用库存归零；历史订单和审计记录会保留。", label: "确认下架", tone: "danger", action: () => updateCommerceInventory(item.id, 0, item.inventory.version) })}>下架商品</button> : null}</div></li>)}</ul> : null}
      {snapshot.seller_orders.length ? <div className="commerceSubsection"><h3>待履约订单</h3>{snapshot.seller_orders.map((order) => <OrderCard order={order} key={order.id} actions={order.status === "paid" ? <button className="productButton" type="button" disabled={busy} onClick={() => setConfirmation({ title: "确认标记为沙盒发货？", description: "订单会进入待收货状态。当前不会创建真实物流单或联系承运商。", label: "确认发货", tone: "primary", action: () => shipCommerceOrder(order.id, order.version, "内部沙盒履约记录，无真实物流单号。") })}>标记沙盒发货</button> : null} />)}</div> : null}
      {snapshot.seller_after_sales.some((item) => item.status === "requested") ? <div className="commerceSubsection"><h3>待处理售后</h3>{snapshot.seller_after_sales.filter((item) => item.status === "requested").map((item) => <div className="commerceDecision" key={item.id}><p>{item.reason}</p><button className="productButton" type="button" disabled={busy} onClick={() => setConfirmation({ title: "确认受理这项内部售后？", description: "只更新可审计售后状态，不代表已完成真实退款。", label: "确认受理", tone: "primary", action: () => decideCommerceAfterSale(item.id, item.version, "approved", "内部沙盒售后已受理，不代表真实退款完成。") })}>受理</button><button className="productButtonSecondary" type="button" disabled={busy} onClick={() => setConfirmation({ title: "确认驳回这项内部售后？", description: "售后状态将记录为已驳回，决定会同步给当前买家。", label: "确认驳回", tone: "danger", action: () => decideCommerceAfterSale(item.id, item.version, "rejected", "内部沙盒售后未通过。") })}>驳回</button></div>)}</div> : null}
    </section> : null}

    {view === "review" && canReview ? <section className="commerceSection">
      <header><div><small>INDEPENDENT PRODUCT REVIEW</small><h2>商品审核</h2><p>审核员不能审核自己的商品；通过仅表示可进入内部交易沙盒。</p></div></header>
      {snapshot.review_queue.length ? <ul className="commerceList">{snapshot.review_queue.map((item) => <li key={item.id}><div><span>卖家 {item.seller_user_id} · v{item.version}</span><h3>{item.title}</h3><p>{item.summary}</p><small>来源说明：{item.source_note}</small></div><div className="commerceRowActions"><button className="productButton" type="button" disabled={busy} onClick={() => setConfirmation({ title: "批准进入内部交易沙盒？", description: "仅批准状态流转，不构成非遗事实、知识产权或商品资质认证。", label: "审核通过", tone: "primary", action: () => reviewCommerceProduct(item.id, "approved", "仅批准进入内部交易沙盒；正式来源与资质仍需线下核验。", item.version) })}>审核通过</button><button className="productButtonSecondary" type="button" disabled={busy} onClick={() => setConfirmation({ title: "退回商品并要求补充资料？", description: "商品不会进入买家目录；卖家可补充来源与授权说明后重新提交。", label: "确认退回", tone: "danger", action: () => reviewCommerceProduct(item.id, "rejected", "资料不足，请补充来源与授权说明。", item.version) })}>退回补充</button></div></li>)}</ul> : <StateNotice kind="empty" title="没有待审核商品" description="卖家提交商品后会出现在这里。" />}
    </section> : null}

    <ConfirmDialog open={Boolean(confirmation)} title={confirmation?.title ?? ""} description={confirmation?.description ?? ""} confirmLabel={confirmation?.label ?? "确认"} tone={confirmation?.tone} busy={busy} onCancel={() => setConfirmation(null)} onConfirm={() => { if (!confirmation) return; void run(confirmation.action, `${confirmation.label}已完成。`).then((success) => { if (success) setConfirmation(null); }); }} />
  </ProductFrame>;
}

function OrderCard({ order, actions }: { order: CommerceOrder; actions: React.ReactNode }) {
  return <li><div><span className="productStatusPill is-warning">{statusLabels[order.status] ?? order.status}</span><h3>{order.items.map((item) => item.title_snapshot).join("、")}</h3><p>{money.format(order.total_cents / 100)} · 订单 {order.id.slice(-8)}</p>{order.payment ? <small>支付渠道：内部沙盒 · 不涉及真实资金</small> : null}{order.fulfillment ? <small>履约：{order.fulfillment.tracking_note}</small> : null}</div><div className="commerceRowActions">{actions}</div></li>;
}
