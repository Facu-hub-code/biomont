import { notFound } from "next/navigation";

import { AgentDecisionGraphTracePanel } from "@/components/agent-decision-graph-trace-panel";
import {
  AgentDecisionRetrievedPanel,
  type RetrievedItemEnriched,
} from "@/components/agent-decision-retrieved-panel";
import type { GraphTraceStepDisplay } from "@/components/agent-decision-graph-trace-panel";
import { CatalogBackLink } from "@/components/catalog-back-link";
import { apiRequest } from "@/lib/api";
import { requireRole } from "@/lib/auth";

type AgentDecisionDetailEnrichment = {
  retrieved_items: RetrievedItemEnriched[];
  graph_trace_display: GraphTraceStepDisplay[];
};

type AgentDecisionDetail = {
  id: string;
  decision: string;
  reasoning: string | null;
  retrieved: Array<Record<string, unknown>>;
  top_similarity: number | null;
  system_prompt_version: number | null;
  graph_trace: Array<Record<string, unknown>>;
  created_at: string;
  message_content: string | null;
  conversation_id: string | null;
  rtc_name: string | null;
  phone_e164: string | null;
  previous_user_message: string | null;
  enrichment: AgentDecisionDetailEnrichment;
};

export default async function AgentDecisionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireRole(["admin", "scientist", "viewer"]);
  const { id } = await params;
  let detail: AgentDecisionDetail;
  try {
    detail = await apiRequest<AgentDecisionDetail>(`/agent-decisions/${id}`);
  } catch {
    notFound();
  }

  const enrichment = detail.enrichment ?? {
    retrieved_items: [],
    graph_trace_display: [],
  };

  return (
    <div className="space-y-8">
      <CatalogBackLink href="/agent-decisions" label="Volver a decisiones" />

      <header className="space-y-1">
        <h2 className="text-2xl font-semibold text-slate-900">Decision {detail.decision}</h2>
        <p className="text-sm text-slate-500">
          {new Date(detail.created_at).toLocaleString()} · {detail.rtc_name ?? "RTC desconocido"} ·{" "}
          {detail.phone_e164 ?? "-"}
        </p>
      </header>

      <section className="card space-y-2">
        <h3 className="text-sm font-semibold text-slate-700">Resumen</h3>
        <p className="text-sm text-slate-700">Similarity: {detail.top_similarity ?? "-"}</p>
        <p className="text-sm text-slate-700">
          Version system prompt: {detail.system_prompt_version ?? "-"}
        </p>
        {detail.conversation_id ? (
          <p className="text-sm text-slate-700">
            Conversacion: <span className="font-mono text-xs">{detail.conversation_id}</span>
          </p>
        ) : null}
      </section>

      <section className="card space-y-2">
        <h3 className="text-sm font-semibold text-slate-700">Contexto de mensajes</h3>
        <p className="text-sm text-slate-700">
          <strong>Usuario previo:</strong> {detail.previous_user_message ?? "-"}
        </p>
        <p className="text-sm text-slate-700 whitespace-pre-wrap">
          <strong>Respuesta asistente:</strong> {detail.message_content ?? "-"}
        </p>
        <p className="text-sm text-slate-700 whitespace-pre-wrap">
          <strong>Reasoning:</strong> {detail.reasoning ?? "-"}
        </p>
      </section>

      <section className="card space-y-3">
        <h3 className="text-sm font-semibold text-slate-700">Retrieved</h3>
        <AgentDecisionRetrievedPanel items={enrichment.retrieved_items} />
      </section>

      <section className="card space-y-3">
        <h3 className="text-sm font-semibold text-slate-700">Graph trace</h3>
        <AgentDecisionGraphTracePanel steps={enrichment.graph_trace_display} />
      </section>
    </div>
  );
}
