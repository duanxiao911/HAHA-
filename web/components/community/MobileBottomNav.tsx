"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCommunity } from "@/lib/community/provider";

const mobileNavigation = [
  { href: "/", label: "首页", icon: "home" },
  { href: "/search", label: "发现", icon: "discover" },
  { href: "/learning", label: "学习", icon: "learn" },
  { href: "/creator", label: "创作", icon: "create" },
  { href: "/notifications", label: "消息", icon: "message" },
  { href: "/profile/demo-user", activePath: "/profile", label: "我的", icon: "profile" },
] as const;

function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/" || pathname === "/community";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavigationIcon({ type }: { type: (typeof mobileNavigation)[number]["icon"] }) {
  const paths = {
    home: <><path d="m3.5 10 8.5-7 8.5 7" /><path d="M5.5 9.2V21h13V9.2M9.5 21v-7h5v7" /></>,
    discover: <><circle cx="12" cy="12" r="9" /><path d="m15.8 8.2-2.1 5.5-5.5 2.1 2.1-5.5 5.5-2.1Z" /></>,
    learn: <><path d="M4 5.5h6.2c1 0 1.8.8 1.8 1.8V20c0-1.2-1-2.2-2.2-2.2H4V5.5Z" /><path d="M20 5.5h-6.2c-1 0-1.8.8-1.8 1.8V20c0-1.2 1-2.2 2.2-2.2H20V5.5Z" /></>,
    create: <><path d="M12 3v18M3 12h18" /><circle cx="12" cy="12" r="9" /></>,
    message: <><path d="M4 5.5h16v11H9l-5 4v-15Z" /><path d="M8 10h8M8 13h5" /></>,
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
  const { snapshot } = useCommunity();
  const profileHref = snapshot.viewer.id
    ? `/profile/${encodeURIComponent(snapshot.viewer.id)}`
    : "/identity";

  return (
    <nav className="productMobileNav" aria-label="移动端主要导航">
      {mobileNavigation.map(({ href, label, icon, ...item }) => {
        const resolvedHref = icon === "profile" ? profileHref : href;
        const activePath = "activePath" in item ? item.activePath : href;
        const active = isActivePath(pathname, activePath);
        return (
          <Link href={resolvedHref} aria-current={active ? "page" : undefined} key={href}>
            <NavigationIcon type={icon} />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export default MobileBottomNav;
