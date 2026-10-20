import type { ReactNode } from "react";

import { AppHeader } from "./AppHeader";
import { MobileBottomNav } from "./MobileBottomNav";

type ProductFrameProps = {
  children: ReactNode;
  className?: string;
  mainClassName?: string;
  initialQuery?: string;
  demoLabel?: string;
  hideMobileNavigation?: boolean;
};

export function ProductFrame({
  children,
  className = "",
  mainClassName = "",
  initialQuery,
  demoLabel,
  hideMobileNavigation = false,
}: ProductFrameProps) {
  const frameClassName = ["productFrame", className].filter(Boolean).join(" ");
  const contentClassName = ["productFrameContent", mainClassName].filter(Boolean).join(" ");

  return (
    <div className={frameClassName}>
      <AppHeader initialQuery={initialQuery} demoLabel={demoLabel} />
      <main className={contentClassName} id="main-content">
        {children}
      </main>
      {hideMobileNavigation ? null : <MobileBottomNav />}
    </div>
  );
}

export default ProductFrame;
