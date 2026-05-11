import { redirect } from "next/navigation";

import { fetchCurrentUser } from "@/lib/auth";

export default async function RootPage() {
  const user = await fetchCurrentUser();
  if (user) redirect("/dashboard");
  redirect("/login");
}
