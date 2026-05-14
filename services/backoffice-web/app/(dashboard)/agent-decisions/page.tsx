import Link from "next/link";

import { apiRequest } from "@/lib/api";
import { requireRole } from "@/lib/auth";

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
    <div className="space-y-8">
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">Decisiones del agente</h2>
        <p className="text-sm text-slate-500">
          Auditoria de decisiones, recuperacion y contexto por conversacion.
        </p>
      </header>

      <form className="card grid grid-cols-1 gap-4 md:grid-cols-4" method="get">
        <div>
          <label className="form-label" htmlFor="decision">
            Decision
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
            Telefono
          </label>
          <input id="phone" name="phone" defaultValue={params.phone ?? ""} className="form-input" />
        </div>
        <div>
          <label className="form-label" htmlFor="conversation_id">
            Conversation ID
          </label>
          <input
            id="conversation_id"
            name="conversation_id"
            defaultValue={params.conversation_id ?? ""}
            className="form-input"
          />
        </div>
        <div className="flex items-end">
          <button type="submit" className="btn-primary">
            Filtrar
          </button>
        </div>
      </form>

      <table className="table-default">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Decision</th>
            <th>RTC</th>
            <th>Telefono</th>
            <th>Similarity</th>
            <th>Preview</th>
            <th />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {response.items.map((row) => (
            <tr key={row.id}>
              <td>{new Date(row.created_at).toLocaleString()}</td>
              <td>{row.decision}</td>
              <td>{row.rtc_name ?? "-"}</td>
              <td className="font-mono text-xs">{row.phone_e164 ?? "-"}</td>
              <td>{row.top_similarity ?? "-"}</td>
              <td className="max-w-md truncate text-slate-600">{row.message_preview ?? "-"}</td>
              <td>
                <Link href={`/agent-decisions/${row.id}`} className="text-biomont-primary hover:underline">
                  Ver detalle
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
