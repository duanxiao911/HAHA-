import type { ReactNode } from "react";

import { COMMUNITY_PROJECTS } from "@/lib/community";

export const dynamicParams = false;

export function generateStaticParams() {
  return COMMUNITY_PROJECTS.flatMap((project) => [{ id: project.id }, { id: project.slug }]);
}

export default function HeritageProjectLayout({ children }: { children: ReactNode }) {
  return children;
}
