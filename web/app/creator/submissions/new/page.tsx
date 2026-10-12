import { Suspense } from "react";

import { StateNotice } from "@/components/community/StateNotice";

import { SubmissionWizardFromRoute } from "./SubmissionWizard";

export const metadata = {
  title: "投稿向导｜HAHA 创作中心",
  description: "本地演示投稿、事实检查与审核状态闭环。",
};

export default function NewSubmissionPage() {
  return (
    <Suspense fallback={<StateNotice kind="loading" title="正在打开投稿向导" description="准备本地演示草稿。" />}>
      <SubmissionWizardFromRoute />
    </Suspense>
  );
}
