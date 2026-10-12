import { Suspense } from "react";

import { StateNotice } from "@/components/community/StateNotice";
import { COMMUNITY_PEOPLE, LOCAL_DEMO_VIEWER_ID } from "@/lib/community";

import { ProfileView } from "./ProfileView";

export function generateStaticParams() {
  return [
    { id: LOCAL_DEMO_VIEWER_ID },
    ...COMMUNITY_PEOPLE.flatMap((person) => [{ id: person.id }, { id: person.slug }]),
  ];
}

export default async function ProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense fallback={<StateNotice kind="loading" title="正在打开文化档案" description="恢复当前浏览器中的本地状态。" />}>
      <ProfileView profileId={decodeURIComponent(id)} />
    </Suspense>
  );
}
