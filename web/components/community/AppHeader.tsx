"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState, useSyncExternalStore } from "react";

import {
  AUTH_REQUIRED,
  BusinessRole,
  DEMO_MODE,
  getAuthSessionSnapshot,
  getIdentityCenter,
  getServerAuthSessionSnapshot,
  IdentitySnapshot,
  initializeAuthSession,
  subscribeAuthSession,
} from "@/lib/api";
import { useCommunity } from "@/lib/community/provider";

type AppHeaderProps = {
  initialQuery?: string;
  demoLabel?: string;
};

const primaryNavigation = [
  { href: "/community", label: "视频社区", paths: ["/community", "/content", "/search", "/map", "/heritage-projects", "/inheritors", "/topics", "/events", "/creator"] },
  { href: "/commerce", label: "非遗电商", paths: ["/commerce"] },
  { href: "/learning", label: "AI 学习", paths: ["/learning"] },
  { href: "/identity", label: "用户中心", paths: ["/identity", "/profile", "/notifications", "/login", "/register"] },
] as const;

const roleLabels: Record<BusinessRole, string> = {
  viewer: "浏览者",
  buyer: "买家",
  learner: "学习者",
  creator: "创作者",
  contributor: "知识贡献者",
  seller: "卖家",
  reviewer: "审核员",
  admin: "管理员",
};

function pathMatches(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

function SearchIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 4.2 4.2" /></svg>;
}

function MessageIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M5 5.5h14v10H9l-4 3.5V5.5Z" /><path d="M8.5 9.5h7M8.5 12.5h4.5" /></svg>;
}

export function AppHeader({ initialQuery = "", demoLabel }: AppHeaderProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { snapshot } = useCommunity();
  const [query, setQuery] = useState(initialQuery);
  const [identity, setIdentity] = useState<IdentitySnapshot | null>(null);
  const [identityMenuOpen, setIdentityMenuOpen] = useState(false);
  const identityMenuRef = useRef<HTMLDivElement>(null);
  const identityTriggerRef = useRef<HTMLButtonElement>(null);
  const authState = useSyncExternalStore(subscribeAuthSession, getAuthSessionSnapshot, getServerAuthSessionSnapshot);
  const signedIn = authState === "authenticated";
  const environmentLabel = demoLabel ?? (snapshot.runtime.mode === "api" ? "内部 API" : "本地演示");

  useEffect(() => { void initializeAuthSession(); }, []);
  useEffect(() => {
    if (DEMO_MODE || (AUTH_REQUIRED && !signedIn)) return;
    let active = true;
    void getIdentityCenter().then((value) => { if (active) setIdentity(value); }).catch(() => { if (active) setIdentity(null); });
    return () => { active = false; };
  }, [signedIn]);
  useEffect(() => {
    if (!identityMenuOpen) return;
    function closeMenu(event: MouseEvent | KeyboardEvent) {
      if (event instanceof KeyboardEvent && event.key !== "Escape") return;
      if (event instanceof MouseEvent && identityMenuRef.current?.contains(event.target as Node)) return;
      setIdentityMenuOpen(false);
      if (event instanceof KeyboardEvent) {
        requestAnimationFrame(() => identityTriggerRef.current?.focus());
      }
    }
    document.addEventListener("mousedown", closeMenu);
    document.addEventListener("keydown", closeMenu);
    return () => { document.removeEventListener("mousedown", closeMenu); document.removeEventListener("keydown", closeMenu); };
  }, [identityMenuOpen]);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanQuery = query.trim();
    router.push(cleanQuery ? `/search?q=${encodeURIComponent(cleanQuery)}` : "/search");
  }

  const visibleIdentity = AUTH_REQUIRED && !signedIn ? null : identity;
  const displayName = DEMO_MODE ? snapshot.viewer.displayName : visibleIdentity?.profile.display_name || "账户";
  const professionalRoles = visibleIdentity?.professional_roles ?? [];
  const professionalSummary = professionalRoles.length
    ? professionalRoles.map((role) => roleLabels[role]).join("、")
    : "按需开通";

  return <header className="productHeader"><div className="productHeaderMain">
    <Link className="productBrand" href="/" aria-label="HAHA 平台首页"><span>HA</span>HA</Link>
    <span className="productEnvironmentBadge" title={snapshot.runtime.dataNotice}><i aria-hidden="true" />{environmentLabel}</span>
    <nav className="productPrimaryNav" aria-label="四大板块">{primaryNavigation.map(({ href, label, paths }) => {
      const active = paths.some((prefix) => pathMatches(pathname, prefix));
      return <Link href={href} aria-current={active ? "page" : undefined} key={href}>{label}</Link>;
    })}</nav>
    <form className="productSearch" role="search" onSubmit={submitSearch}>
      <label className="productVisuallyHidden" htmlFor="product-global-search">搜索非遗内容、项目、人物和地区</label>
      <input id="product-global-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索非遗内容、项目、人物和地区" />
      <button type="submit" aria-label="提交搜索"><SearchIcon /></button>
    </form>
    <nav className="productUtilityNav" aria-label="账户功能">
      <Link className="productMessageAction" href="/notifications" aria-label="消息与通知" aria-current={pathMatches(pathname, "/notifications") ? "page" : undefined}><MessageIcon /><span>消息</span></Link>
      <div className="productIdentityMenu" ref={identityMenuRef}>
        {signedIn || !AUTH_REQUIRED ? <button className="productIdentityTrigger" ref={identityTriggerRef} type="button" aria-haspopup="menu" aria-expanded={identityMenuOpen} aria-controls="product-identity-menu" onClick={() => setIdentityMenuOpen((open) => !open)}>
          <span className="productIdentityAvatar" aria-hidden="true">{displayName.slice(0, 1).toUpperCase()}</span><span className="productIdentityCopy"><small>我的 HAHA</small><strong>{displayName}</strong></span><b aria-hidden="true">⌄</b>
        </button> : <Link className="productLoginAction" href="/login">登录</Link>}
        {identityMenuOpen ? <div className="productIdentityPopover" id="product-identity-menu" role="menu">
          <div className="productIdentityPopoverHead"><small>当前账户</small><strong>{displayName}</strong></div>
          <div className="productIdentityPopoverHint" role="presentation"><strong>专业工作台</strong><span>{professionalSummary}</span></div>
          <Link role="menuitem" href={DEMO_MODE ? "/profile/demo-user" : "/identity"} onClick={() => setIdentityMenuOpen(false)}>{DEMO_MODE ? "查看本地演示档案" : "用户中心"}</Link>
          {!DEMO_MODE ? <Link role="menuitem" href="/identity?tab=assets" onClick={() => setIdentityMenuOpen(false)}>我的内容</Link> : null}
          {!DEMO_MODE ? <Link role="menuitem" href="/identity?manage=roles" onClick={() => setIdentityMenuOpen(false)}>专业工作台</Link> : null}
          <Link role="menuitem" href="/notifications" onClick={() => setIdentityMenuOpen(false)}>消息与通知</Link>
          {!DEMO_MODE ? <Link role="menuitem" href="/identity?tab=settings" onClick={() => setIdentityMenuOpen(false)}>设置与安全</Link> : null}
        </div> : null}
      </div>
    </nav>
  </div></header>;
}

export default AppHeader;
