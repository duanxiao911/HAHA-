"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const mobileNavigation = [
  { href: "/", label: "首页", icon: "home" },
  { href: "/community", label: "社区", icon: "community", paths: ["/community", "/content", "/search", "/map", "/heritage-projects", "/inheritors", "/topics", "/events", "/creator"] },
  { href: "/learning", label: "学习", icon: "learn" },
  { href: "/commerce", label: "电商", icon: "commerce" },
  { href: "/identity", label: "我的", icon: "profile", paths: ["/identity", "/profile", "/notifications", "/login"] },
] as const;

function isActivePath(pathname: string, href: string, paths?: readonly string[]): boolean {
  if (href === "/") return pathname === "/";
  return (paths ?? [href]).some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

function NavigationIcon({ type }: { type: (typeof mobileNavigation)[number]["icon"] }) {
  const paths = {
    home: <><path d="m3.5 10 8.5-7 8.5 7" /><path d="M5.5 9.2V21h13V9.2M9.5 21v-7h5v7" /></>,
    community: <><rect x="3" y="5" width="18" height="14" rx="3" /><path d="m10 9 5 3-5 3V9Z" /></>,
    learn: <><path d="M4 5.5h6.2c1 0 1.8.8 1.8 1.8V20c0-1.2-1-2.2-2.2-2.2H4V5.5Z" /><path d="M20 5.5h-6.2c-1 0-1.8.8-1.8 1.8V20c0-1.2 1-2.2 2.2-2.2H20V5.5Z" /></>,
    commerce: <><path d="M4 8h16l-1 12H5L4 8Z" /><path d="M8 8a4 4 0 0 1 8 0M8 12h.01M16 12h.01" /></>,
    profile: <><circle cx="12" cy="8.2" r="3.2" /><path d="M5.5 20c.6-4.1 3-6.1 6.5-6.1s5.9 2 6.5 6.1" /></>,
  };

  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      {paths[type]}
    </svg>
  );
}

export function MobileBottomNav() {
  const pathname = usePathname();

  return (
    <nav className="productMobileNav" aria-label="移动端主要导航">
      {mobileNavigation.map(({ href, label, icon, ...item }) => {
        const paths = "paths" in item ? item.paths : undefined;
        const active = isActivePath(pathname, href, paths);
        return (
          <Link href={href} aria-current={active ? "page" : undefined} key={href}>
            <NavigationIcon type={icon} />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export default MobileBottomNav;
