import type { ReactNode } from "react";

import { COMMUNITY_PEOPLE } from "@/lib/community";

export const dynamicParams = false;

export function generateStaticParams() {
  return COMMUNITY_PEOPLE.flatMap((person) => [{ id: person.id }, { id: person.slug }]);
}

export default function InheritorLayout({ children }: { children: ReactNode }) {
  return children;
}
