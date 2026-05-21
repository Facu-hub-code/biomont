import { ActionFeedbackForm } from "@/components/action-feedback-form";
import { SubmitButton } from "@/components/submit-button";
import { apiRequest } from "@/lib/api";

import { updateTicketAction } from "./actions";

type Ticket = {
  id: string;
  type: "no_info" | "low_confidence" | "user_request";
  status: "open" | "in_progress" | "resolved" | "wont_fix";
  summary: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

function statusTone(status: Ticket["status"]) {
  switch (status) {
    case "open":
      return "border-amber-200/90 bg-amber-50 text-amber-950 ring-amber-400/15";
    case "resolved":
      return "border-emerald-200/90 bg-emerald-50 text-emerald-950 ring-emerald-400/15";
    default:
      return "border-zinc-200 bg-zinc-100 text-zinc-800 ring-zinc-400/15";
  }
}

export default async function TicketsPage({
  searchParams,
}: {
  searchParams?: Promise<{ status?: string }>;
}) {
  const params = (await searchParams) ?? {};
  const path = params.status ? `/tickets?status=${params.status}` : "/tickets";
  const tickets = await apiRequest<Ticket[]>(path);

  const chips: { status: string; label: string }[] = [
    { status: "", label: "Todos" },
    { status: "open", label: "Abiertos" },
    { status: "in_progress", label: "En curso" },
    { status: "resolved", label: "Resueltos" },
  ];

  return (
    <div className="space-y-10">
      <header className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="page-header">
          <h2 className="page-title">Tickets</h2>
          <p className="page-subtitle">
            Escalamientos donde el agente no encontró información o no alcanzó confianza suficiente.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {chips.map(({ status, label }) => {
            const active = (params.status ?? "") === status;
            return (
              <a
                key={status || "all"}
                href={status ? `?status=${status}` : "?"}
                className={`filter-chip ${active ? "filter-chip-active" : ""}`}
              >
                {label}
              </a>
            );
          })}
        </div>
      </header>

      <ul className="grid gap-4">
        {tickets.map((ticket) => (
          <li key={ticket.id} className="card-static border-white/90 p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0 flex-1 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1 font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-600 ring-1 ring-zinc-100">
                    {ticket.type.replace("_", " ")}
                  </span>
                  <span
                    className={`badge rounded-lg border px-3 py-1 text-[11px] font-bold uppercase tracking-wide ring-1 ${statusTone(ticket.status)}`}
                  >
                    {ticket.status.replace("_", " ")}
                  </span>
                </div>
                <p className="text-base font-medium leading-snug text-zinc-900">{ticket.summary}</p>
                {ticket.notes ? (
                  <p className="text-sm leading-relaxed text-zinc-600">{ticket.notes}</p>
                ) : null}
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-400">
                  Creado {new Date(ticket.created_at).toLocaleString()}
                </p>
              </div>
              <ActionFeedbackForm action={updateTicketAction} successMessage="Ticket actualizado.">
                <div className="flex flex-col gap-3 rounded-2xl bg-zinc-50/95 p-4 ring-1 ring-zinc-100 lg:min-w-[220px]">
                  <input type="hidden" name="id" value={ticket.id} />
                  <label className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
                    Estado
                  </label>
                  <select name="status" defaultValue={ticket.status} className="form-input mt-0 py-2 text-sm">
                    <option value="open">open</option>
                    <option value="in_progress">in_progress</option>
                    <option value="resolved">resolved</option>
                    <option value="wont_fix">wont_fix</option>
                  </select>
                  <SubmitButton
                    label="Actualizar"
                    pendingLabel="Guardando…"
                    variant="secondary"
                    className="justify-center py-2 text-xs"
                  />
                </div>
              </ActionFeedbackForm>
            </div>
          </li>
        ))}
      </ul>

      {tickets.length === 0 ? (
        <div className="rounded-[28px] border border-dashed border-zinc-300/90 bg-white/70 px-8 py-16 text-center backdrop-blur-sm">
          <p className="text-sm font-semibold text-zinc-700">No hay tickets con este filtro</p>
          <p className="mt-2 text-sm text-zinc-500">Buena señal: menos fricción en las respuestas del agente.</p>
        </div>
      ) : null}
    </div>
  );
}
