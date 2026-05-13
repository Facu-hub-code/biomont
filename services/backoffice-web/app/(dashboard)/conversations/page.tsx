import { requireUser } from "@/lib/auth";

import ConversationsClient from "./conversations-client";

export const dynamic = "force-dynamic";

export default async function ConversationsPage() {
  const user = await requireUser();
  const canPlayground = user.role === "admin" || user.role === "scientist";
  return <ConversationsClient canPlayground={canPlayground} />;
}
