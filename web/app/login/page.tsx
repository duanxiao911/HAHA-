import type { Metadata } from "next";
import { LoginForm } from "./LoginForm";

export const metadata: Metadata = {
  title: "账户登录｜HAHA 非遗社区",
  description: "登录 HAHA，继续观看、学习、收藏和购物。",
};

export default function LoginPage() { return <LoginForm />; }
