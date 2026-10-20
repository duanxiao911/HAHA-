"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { ProductFrame } from "@/components/community/ProductFrame";
import {
  AUTH_REQUIRED,
  getAuthSessionSnapshot,
  getServerAuthSessionSnapshot,
  initializeAuthSession,
  loginAccount,
  logoutAccount,
  subscribeAuthSession,
} from "@/lib/api";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const authState = useSyncExternalStore(
    subscribeAuthSession, getAuthSessionSnapshot, getServerAuthSessionSnapshot,
  );
  const signedIn = authState === "authenticated";
  useEffect(() => { void initializeAuthSession(); }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    try { await loginAccount(email, password); router.replace("/identity"); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "登录失败，请稍后重试。"); }
    finally { setBusy(false); }
  }

  async function signOut() {
    setBusy(true); setError("");
    try { await logoutAccount(); router.refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "退出失败，请稍后重试。"); }
    finally { setBusy(false); }
  }

  return <ProductFrame hideMobileNavigation>
    <div className="authLoginLayout">
      <section className="productPanel authAccountPanel"><div className="productPanelBody">
        <small className="productEyebrow">欢迎回来</small>
        <h1>{signedIn ? "你已经登录" : "登录 HAHA"}</h1>
        <p>继续观看、学习、收藏和购物。专业工作台也使用同一个账户。</p>
        {!AUTH_REQUIRED ? <div className="productInlineAlert">当前是静态或开发演示，真实登录仅在安全账户环境开放。</div> : null}
        {error ? <div className="identityAlert" role="alert">{error}</div> : null}
        {authState === "unknown" ? <div className="productInlineAlert">正在验证安全会话…</div> : signedIn ? <div className="productFormActions"><Link className="productButton" href="/identity">进入用户中心</Link><button className="productButtonSecondary" type="button" disabled={busy} onClick={() => void signOut()}>{busy ? "正在退出…" : "退出当前会话"}</button></div> :
          <form className="authLoginForm" onSubmit={submit}>
            <label>邮箱<input type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
            <label>密码<span className="authPasswordField"><input type={showPassword ? "text" : "password"} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /><button type="button" aria-label={showPassword ? "隐藏密码" : "显示密码"} onClick={() => setShowPassword((value) => !value)}>{showPassword ? "隐藏" : "显示"}</button></span></label>
            <button className="productButton" type="submit" disabled={busy || !AUTH_REQUIRED}>{busy ? "正在登录…" : "登录"}</button>
            <div className="authFormFooter"><span>还没有账户？</span><Link href="/register">创建账户</Link></div>
            <small className="authRecoveryNote">找回密码将在接入邮件验证服务后开放。</small>
          </form>}
      </div></section>
      <aside className="productSidePanel authBenefitPanel"><small>一个账户，持续积累</small><h2>回到你的非遗文化空间</h2><ul><li>继续上次观看和学习</li><li>管理收藏、想学与关注</li><li>查看订单与售后状态</li><li>进入已经开通的专业工作台</li></ul><p>平台不会要求普通用户在“买家、学习者、浏览者”之间切换。</p></aside>
    </div>
  </ProductFrame>;
}
