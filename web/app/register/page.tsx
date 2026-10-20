import type { Metadata } from "next";
import { RegisterForm } from "./RegisterForm";

export const metadata: Metadata = {
  title: "创建账户｜HAHA 非遗社区",
  description: "创建统一 HAHA 账户，使用观看、学习、收藏和购物能力。",
};

export default function RegisterPage() { return <RegisterForm />; }
