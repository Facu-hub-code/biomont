import Link from "next/link";

import { ChevronRight } from "lucide-react";

import { apiRequest } from "@/lib/api";
import { requireRole } from "@/lib/auth";

import { AgentDecisionsFilterForm } from "./agent-decisions-filter-form";

type AgentDecision = {
  id: string;
  decision: "answered" | "low_confidence" | "no_match" | "blocked" | "error";
  created_at: string;
  rtc_name: string | null;
  phone_e164: string | null;
  conversation_id: string | null;
  top_similarity: number | null;
  message_preview: string | null;
};

type AgentDecisionListResponse = {
  items: AgentDecision[];
  page: number;
  page_size: number;
  total: number;
};

function decisionStyles(decision: AgentDecision["decision"]) {
  switch (decision) {
    case "answered":
      return "border-emerald-200/90 bg-emerald-50/95 text-emerald-900 ring-emerald-500/15";
    case "no_match":
      return "border-rose-200/90 bg-rose-50/95 text-rose-900 ring-rose-500/15";
    case "low_confidence":
      return "border-amber-200/90 bg-amber-50/95 text-amber-950 ring-amber-500/15";
    case "blocked":
      return "border-zinc-300 bg-zinc-100 text-zinc-800 ring-zinc-400/15";
    default:
      return "border-red-200/90 bg-red-50 text-red-900 ring-red-400/15";
  }
}

export default async function AgentDecisionsPage({
  searchParams,
}: {
  searchParams?: Promise<{
    decision?: string;
    phone?: string;
    conversation_id?: string;
  }>;
}) {
  await requireRole(["admin", "scientist", "viewer"]);
  const params = (await searchParams) ?? {};
  const query = new URLSearchParams();
  query.set("page", "1");
  query.set("page_size", "100");
  if (params.decision) query.set("decision", params.decision);
  if (params.phone) query.set("phone", params.phone);
  if (params.conversation_id) query.set("conversation_id", params.conversation_id);
  const response = await apiRequest<AgentDecisionListResponse>(`/agent-decisions?${query.toString()}`);

  return (
    <div className="space-y-10">
      <header className="page-header">
        <h2 className="page-title">Decisiones del agente</h2>
        <p className="page-subtitle">
          Auditoría de retrieval, umbrales y trazas por mensaje — vista tipo inbox para revisión rápida.
        </p>
      </header>

      <AgentDecisionsFilterForm>
        <div>
          <label className="form-label" htmlFor="decision">
            Decisión
          </label>
          <select id="decision" name="decision" defaultValue={params.decision ?? ""} className="form-input">
            <option value="">Todas</option>
            <option value="answered">answered</option>
            <option value="low_confidence">low_confidence</option>
            <option value="no_match">no_match</option>
            <option value="blocked">blocked</option>
            <option value="error">error</option>
          </select>
        </div>
        <div>
          <label className="form-label" htmlFor="phone">
            Teléfono
          </label>
          <input id="phone" name="phone" defaultValue={params.phone ?? ""} className="form-input font-mono text-xs" />
        </div>
        <div>
          <label className="form-label" htmlFor="conversation_id">
            Conversation ID
          </label>
          <input
            id="conversation_id"
            name="conversation_id"
            defaultValue={params.conversation_id ?? ""}
            className="form-input font-mono text-xs"
          />
        </div>
      </AgentDecisionsFilterForm>

      <ul className="grid gap-4">
        {response.items.map((row) => (
          <li key={row.id}>
            <Link
              href={`/agent-decisions/${row.id}`}
              className="group card-static flex flex-col gap-4 border-white/90 p-5 transition-all duration-300 hover:border-teal-300/45 hover:shadow-lift md:flex-row md:items-center md:justify-between"
            >
              <div className="min-w-0 flex-1 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`badge rounded-lg border px-3 py-1 font-mono text-[11px] font-bold uppercase tracking-wide ring-1 ${decisionStyles(row.decision)}`}
                  >
                    {row.decision}
                  </span>
                  <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
                    {new Date(row.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="line-clamp-2 text-sm leading-relaxed text-zinc-700">
                  {row.message_preview ?? "—"}
                </p>
                <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-zinc-500">
                  <span>
                    <span className="font-semibold text-zinc-600">RTC:</span>{" "}
                    {row.rtc_name ?? "—"}
                  </span>
                  <span className="font-mono">{row.phone_e164 ?? "—"}</span>
                  <span className="tabular-nums">
                    <span className="font-semibold text-zinc-600">sim:</span>{" "}
                    {row.top_similarity != null ? row.top_similarity.toFixed(3) : "—"}
                  </span>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2 self-end md:self-center">
                <span className="text-sm font-semibold text-teal-700 opacity-90 transition group-hover:text-teal-800">
                  Ver traza
                </span>
                <ChevronRight className="h-5 w-5 text-zinc-300 transition group-hover:translate-x-0.5 group-hover:text-teal-600" />
              </div>
            </Link>
          </li>
        ))}
      </ul>

      {response.items.length === 0 ? (
        <div className="rounded-[28px] border border-dashed border-zinc-300/90 bg-white/70 px-8 py-16 text-center shadow-inner backdrop-blur-sm">
          <p className="text-sm font-semibold text-zinc-700">Sin decisiones para estos filtros</p>
          <p className="mt-2 text-sm text-zinc-500">Probá ampliar la búsqueda o cambiar el tipo de decisión.</p>
        </div>
      ) : null}
    </div>
  );
}
