"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState, useSyncExternalStore } from "react";

import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import {
  AUTH_REQUIRED,
  askCommerceAdvisor,
  CommerceAdvisorSnapshot,
  getAuthSessionSnapshot,
  getCommerceAdvisor,
  getServerAuthSessionSnapshot,
  initializeAuthSession,
  subscribeAuthSession,
} from "@/lib/api";

const money = new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY" });
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : "AI 导购暂时无法响应，请稍后重试。";

export function CommerceAdvisor() {
  const authState = useSyncExternalStore(subscribeAuthSession, getAuthSessionSnapshot, getServerAuthSessionSnapshot);
  const canLoad = !AUTH_REQUIRED || authState === "authenticated";
  const [snapshot, setSnapshot] = useState<CommerceAdvisorSnapshot | null>(null);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!canLoad) return;
    setError("");
    try { setSnapshot(await getCommerceAdvisor()); }
    catch (cause) { setError(errorText(cause)); }
  }, [canLoad]);

  useEffect(() => { void initializeAuthSession(); }, []);
  useEffect(() => {
    if (!canLoad) return;
    let active = true;
    void getCommerceAdvisor()
      .then((value) => { if (active) setSnapshot(value); })
      .catch((cause: unknown) => { if (active) setError(errorText(cause)); });
    return () => { active = false; };
  }, [canLoad]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const value = question.trim();
    if (value.length < 2) { setError("请至少描述两个字的需求。"); return; }
    setBusy(true); setError("");
    try { setSnapshot(await askCommerceAdvisor(value)); setQuestion(""); }
    catch (cause) { setError(errorText(cause)); }
    finally { setBusy(false); }
  }

  if (AUTH_REQUIRED && authState === "unknown") return <ProductFrame><StateNotice kind="loading" title="正在验证安全会话" description="导购记录只向当前账户开放。" /></ProductFrame>;
  if (AUTH_REQUIRED && authState === "anonymous") return <ProductFrame><StateNotice kind="forbidden" title="请先登录文化账户" description="登录后可获得基于真实商品目录的导购建议。" actionLabel="前往登录" actionHref="/login" /></ProductFrame>;
  if (!snapshot) return <ProductFrame mainClassName="commercePage">{error ? <StateNotice kind="error" title="AI 导购暂不可用" description={error} actionLabel="重试" onAction={() => void load()} /> : <StateNotice kind="loading" title="正在连接智能导购" description="检查真实模型与商品目录状态。" />}</ProductFrame>;

  return <ProductFrame className="commerceFrame" mainClassName="commercePage" demoLabel="AI ADVISOR · CATALOG GROUNDED">
    <Link className="commerceBackLink" href="/commerce">← 返回商城</Link>
    <section className="commerceAdvisorShell">
      <aside className="commerceAdvisorIntro">
        <small>HAHA SHOPPING ADVISOR</small>
        <h1>你好，我是你的非遗好物导购</h1>
        <p>告诉我使用场景、预算、送礼对象或喜欢的工艺。我只会推荐当前目录里的真实商品，不会代你下单或付款。</p>
        <div className={`commerceAdvisorStatus is-${snapshot.advisor.status}`}><b>{snapshot.advisor.status === "available" ? "真实模型已连接" : "当前未开放"}</b><span>{snapshot.advisor.reason}</span></div>
        <ul><li>商品范围：服务端当前可售目录</li><li>决策权限：仅建议，不执行交易</li><li>记录范围：当前账户，可刷新恢复</li></ul>
      </aside>
      <div className="commerceConversation">
        <div className="commerceMessages" aria-live="polite">
          {!snapshot.history.length ? <div className="commerceMessage is-assistant"><b>导购说明</b><p>可以这样问：“想送长辈一件 200 元内、适合日常使用的礼物。”</p></div> : null}
          {[...snapshot.history].reverse().map((item) => <div className="commerceExchange" key={item.id}>
            <div className="commerceMessage is-user"><b>你</b><p>{item.question}</p></div>
            <div className="commerceMessage is-assistant"><b>AI 导购</b><p>{item.answer}</p><small>{item.model} · {item.mode === "catalog_grounded_model" ? "目录约束回答" : "未调用模型"}</small>
              {item.recommendations.length ? <div className="commerceAdvisorProducts">{item.recommendations.map(({ product, reason }) => <Link href={`/commerce/products/${encodeURIComponent(product.id)}`} key={product.id}><span>{product.category?.name ?? "非遗好物"}</span><b>{product.title}</b><p>{reason}</p><strong>{money.format(product.price_cents / 100)}</strong></Link>)}</div> : null}
              {item.suggestions.length ? <div className="commerceAdvisorSuggestions">{item.suggestions.map((value) => <button type="button" onClick={() => setQuestion(value)} key={value}>{value}</button>)}</div> : null}
            </div>
          </div>)}
          {busy ? <div className="commerceMessage is-assistant"><b>AI 导购</b><p>正在核对商品目录并整理建议…</p></div> : null}
        </div>
        {error ? <div className="commerceAlert" role="alert">{error}</div> : null}
        <form className="commerceAdvisorComposer" onSubmit={submit}>
          <label htmlFor="advisor-question">描述你的需求</label>
          <div><textarea id="advisor-question" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={1000} placeholder="预算、用途、对象、偏好……" disabled={busy || snapshot.advisor.status !== "available"} /><button className="productButton" disabled={busy || snapshot.advisor.status !== "available" || question.trim().length < 2}>{busy ? "正在寻找" : "发送"}</button></div>
          <small>AI 建议可能出错；价格、库存与来源信息以商品详情和服务端结算校验为准。</small>
        </form>
      </div>
    </section>
  </ProductFrame>;
}
