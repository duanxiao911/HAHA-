import { redirect } from "next/navigation";

export default function CommerceManagePage() {
  redirect("/commerce?view=seller");
}
