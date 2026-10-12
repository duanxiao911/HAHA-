"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

type AppHeaderProps = {
  initialQuery?: string;
  demoLabel?: string;
};

const primaryNavigation = [
  { href: "/", label: "首页", exact: true },
  { href: "/search?type=video", activePath: "/search", label: "非遗影像" },
  { href: "/map", label: "文化地图" },
  { href: "/heritage-projects", label: "项目库" },
  { href: "/inheritors", label: "传承人" },
  { href: "/topics", label: "专题" },
  { href: "/events", label: "活动" },
] as const;

function isActivePath(pathname: string, href: string, exact = false): boolean {
  if (href === "/") return pathname === "/" || pathname === "/community";
  if (exact) return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function SearchIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="10.8" cy="10.8" r="6.8" />
      <path d="m16 16 4.2 4.2" />
    </svg>
  );
}

export function AppHeader({ initialQuery = "", demoLabel = "本地演示" }: AppHeaderProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [query, setQuery] = useState(initialQuery);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanQuery = query.trim();
    router.push(cleanQuery ? `/search?q=${encodeURIComponent(cleanQuery)}` : "/search");
  }

  return (
    <header className="productHeader">
      <div className="productHeaderMain">
        <Link className="productBrand" href="/" aria-label="HAHA 首页">
          <span>HA</span>HA
        </Link>

        <span className="productEnvironmentBadge" title="当前数据保存在本地演示环境中">
          <i aria-hidden="true" />
          {demoLabel}
        </span>

        <nav className="productPrimaryNav" aria-label="主要导航">
          {primaryNavigation.map(({ href, label, ...item }) => {
            const activePath = "activePath" in item ? item.activePath : href;
            const exact = "exact" in item ? item.exact : false;
            const active = isActivePath(pathname, activePath, exact);
            return (
              <Link href={href} aria-current={active ? "page" : undefined} key={href}>
                {label}
              </Link>
            );
          })}
        </nav>

        <form className="productSearch" role="search" onSubmit={submitSearch}>
          <label className="productVisuallyHidden" htmlFor="product-global-search">
            搜索非遗内容、项目、人物和地区
          </label>
          <input
            id="product-global-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索非遗、人物或地区"
          />
          <button type="submit" aria-label="提交搜索">
            <SearchIcon />
          </button>
        </form>

        <nav className="productUtilityNav" aria-label="用户功能">
          <Link
            href="/notifications"
            aria-current={isActivePath(pathname, "/notifications") ? "page" : undefined}
          >
            消息
          </Link>
          <Link
            href="/profile/demo-user"
            aria-current={isActivePath(pathname, "/profile") ? "page" : undefined}
          >
            我的
          </Link>
          <Link
            href="/creator"
            aria-current={isActivePath(pathname, "/creator") ? "page" : undefined}
          >
            创作中心
          </Link>
          <Link className="productSubmitAction" href="/creator/submissions/new">
            ＋ 投稿
          </Link>
          <Link className="productLoginAction" href="/login">
            登录
          </Link>
        </nav>
      </div>
    </header>
  );
}

export default AppHeader;
