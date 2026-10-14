import type { Metadata } from "next";
import { LoginForm } from "./LoginForm";

export const metadata: Metadata = {
  title: "账户登录｜HAHA 非遗社区",
  description: "登录 HAHA 内部测试账户并进入跨设备文化账户。",
};

export default function LoginPage() { return <LoginForm />; }
