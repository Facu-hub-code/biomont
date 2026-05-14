"use client";

import type { FormEvent, ReactNode } from "react";
import { useTransition } from "react";
import { useRouter } from "next/navigation";

export function AgentDecisionsFilterForm({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const q = new URLSearchParams();
    q.set("page", "1");
    q.set("page_size", "100");
    const decision = String(fd.get("decision") ?? "").trim();
    const phone = String(fd.get("phone") ?? "").trim();
    const conversationId = String(fd.get("conversation_id") ?? "").trim();
    if (decision) q.set("decision", decision);
    if (phone) q.set("phone", phone);
    if (conversationId) q.set("conversation_id", conversationId);
    const qs = q.toString();
    startTransition(() => {
      router.push(qs ? `/agent-decisions?${qs}` : "/agent-decisions");
    });
  }

  return (
    <form className="contents" onSubmit={onSubmit}>
      <div className="card grid grid-cols-1 gap-4 md:grid-cols-4">
        {children}
        <div className="flex items-end">
          <button
            type="submit"
            className="btn-primary disabled:cursor-wait"
            disabled={isPending}
            aria-busy={isPending}
          >
            {isPending ? (
              <span className="inline-flex items-center gap-2">
                <span
                  className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
                  aria-hidden
                />
                Cargando…
              </span>
            ) : (
              "Filtrar"
            )}
          </button>
        </div>
      </div>
    </form>
  );
}
