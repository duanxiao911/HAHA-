import { Suspense } from "react";

import { StateNotice } from "@/components/community/StateNotice";

import { SearchExperienceFromRoute } from "./SearchExperience";

export const metadata = {
  title: "搜索｜HAHA 非遗社区",
  description: "搜索非遗内容、项目、人物与地区。",
};

export default function SearchPage() {
  return (
    <Suspense fallback={<StateNotice kind="loading" title="正在打开搜索" description="准备本地演示索引。" />}>
      <SearchExperienceFromRoute />
    </Suspense>
  );
}
