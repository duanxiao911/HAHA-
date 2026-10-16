import type { Metadata } from "next";

import { LearningCenter } from "./LearningCenter";

export const metadata: Metadata = {
  title: "学习成长中心｜HAHA",
  description: "管理真实学习路径、知识卡、测验、每日任务、连续学习与成就。",
};

export default function LearningCenterPage() {
  return <LearningCenter />;
}
