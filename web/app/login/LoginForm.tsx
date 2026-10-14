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
  const [workspace, setWorkspace] = useState("");
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
    try { await loginAccount(email, password, workspace); router.replace("/identity"); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "登录失败，请稍后重试。"); }
    finally { setBusy(false); }
  }

  async function signOut() {
    setBusy(true); setError("");
    try { await logoutAccount(); router.refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "退出失败，请稍后重试。"); }
    finally { setBusy(false); }
  }

  return <ProductFrame demoLabel={AUTH_REQUIRED ? "HttpOnly 安全会话 G3" : "本机开发认证"}>
    <div className="productSearchLayout authLoginLayout">
      <section className="productPanel"><div className="productPanelBody">
        <small className="productEyebrow">SECURE INTERNAL ACCOUNT</small>
        <h1>{signedIn ? "当前浏览器已有登录会话" : "登录你的 HAHA 文化账户"}</h1>
        <p>用于内部测试、独立开发和展示的受控账户。平台不开放公众注册，也不会把登录密码写入日志或浏览器存储。</p>
        {!AUTH_REQUIRED ? <div className="productInlineAlert">当前完整栈运行在显式开发认证模式；切换到 JWT 环境后，本页会启用真实会话。</div> : null}
        {error ? <div className="identityAlert" role="alert">{error}</div> : null}
        {authState === "unknown" ? <div className="productInlineAlert">正在验证安全会话…</div> : signedIn ? <div className="productFormActions"><Link className="productButton" href="/identity">进入用户中心</Link><button className="productButtonSecondary" type="button" disabled={busy} onClick={() => void signOut()}>{busy ? "正在退出…" : "退出当前会话"}</button></div> :
          <form className="authLoginForm" onSubmit={submit}>
            <label>邮箱<input type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
            <label>工作空间<input autoComplete="organization" value={workspace} onChange={(event) => setWorkspace(event.target.value)} required /></label>
            <label>密码<span className="authPasswordField"><input type={showPassword ? "text" : "password"} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /><button type="button" aria-label={showPassword ? "隐藏密码" : "显示密码"} onClick={() => setShowPassword((value) => !value)}>{showPassword ? "隐藏" : "显示"}</button></span></label>
            <button className="productButton" type="submit" disabled={busy || !AUTH_REQUIRED}>{busy ? "正在验证…" : "安全登录"}</button>
          </form>}
      </div></section>
      <aside className="productSidePanel"><h2>G3 会话保护</h2><ul><li>令牌只保存在 HttpOnly Cookie</li><li>同源 BFF 自动轮换短期会话</li><li>变更请求同时执行 CSRF 校验</li><li>退出或撤销后访问立即失效</li><li>最终权限仍由数据库成员关系决定</li></ul><p>当前仅面向内部测试与受控展示，不开放公众注册。</p></aside>
    </div>
  </ProductFrame>;
}
