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
  registerAccount,
  subscribeAuthSession,
} from "@/lib/api";

export function RegisterForm() {
  const router = useRouter();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const authState = useSyncExternalStore(
    subscribeAuthSession, getAuthSessionSnapshot, getServerAuthSessionSnapshot,
  );
  useEffect(() => { void initializeAuthSession(); }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (password !== confirmation) {
      setError("两次输入的密码不一致。");
      return;
    }
    setBusy(true);
    try {
      await registerAccount(displayName, email, password);
      router.replace("/identity");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "注册失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  }

  return <ProductFrame hideMobileNavigation>
    <div className="authLoginLayout">
      <section className="productPanel authAccountPanel"><div className="productPanelBody">
        <small className="productEyebrow">加入 HAHA</small>
        <h1>{authState === "authenticated" ? "你已经拥有账户" : "创建文化账户"}</h1>
        <p>注册后即可浏览、学习、收藏和购物，不需要预先选择身份。</p>
        {!AUTH_REQUIRED ? <div className="productInlineAlert">静态演示不创建真实账户，请在完整安全环境中使用注册。</div> : null}
        {AUTH_REQUIRED ? <div className="productInlineAlert">当前开放受控演示账户；邮箱验证、找回密码和正式用户协议仍待生产接入。</div> : null}
        {error ? <div className="identityAlert" role="alert">{error}</div> : null}
        {authState === "authenticated" ? <div className="productFormActions"><Link className="productButton" href="/identity">进入用户中心</Link></div> :
          <form className="authLoginForm" onSubmit={submit}>
            <label>昵称<input type="text" autoComplete="nickname" minLength={2} maxLength={40} value={displayName} onChange={(event) => setDisplayName(event.target.value)} required /></label>
            <label>邮箱<input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
            <label>密码<span className="authPasswordField"><input type={showPassword ? "text" : "password"} autoComplete="new-password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required /><button type="button" aria-label={showPassword ? "隐藏密码" : "显示密码"} onClick={() => setShowPassword((value) => !value)}>{showPassword ? "隐藏" : "显示"}</button></span><small>至少 12 个字符，建议使用密码管理器生成。</small></label>
            <label>确认密码<input type={showPassword ? "text" : "password"} autoComplete="new-password" minLength={12} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required /></label>
            <button className="productButton" type="submit" disabled={busy || !AUTH_REQUIRED}>{busy ? "正在创建…" : "创建账户"}</button>
            <div className="authFormFooter"><span>已经有账户？</span><Link href="/login">返回登录</Link></div>
          </form>}
      </div></section>
      <aside className="productSidePanel authBenefitPanel"><small>默认能力</small><h2>先使用，再决定是否成为专业创作者</h2><ul><li>浏览和收藏非遗内容</li><li>加入学习路径并保存进度</li><li>使用购物车和订单服务</li><li>需要时再开通创作、商家或贡献工作台</li></ul><p>审核员和管理员属于平台内部权限，不向公众开放申请。</p></aside>
    </div>
  </ProductFrame>;
}
