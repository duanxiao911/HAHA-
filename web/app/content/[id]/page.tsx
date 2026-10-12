import { COMMUNITY_CONTENTS } from "@/lib/community";

import { ContentDetailView } from "./ContentDetailView";

export function generateStaticParams() {
  return COMMUNITY_CONTENTS.map((content) => ({ id: content.id }));
}

export default async function ContentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ContentDetailView contentId={id} />;
}
