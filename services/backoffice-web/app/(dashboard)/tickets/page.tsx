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

export default async function TicketsPage({
  searchParams,
}: {
  searchParams?: Promise<{ status?: string }>;
}) {
  const params = (await searchParams) ?? {};
  const path = params.status ? `/tickets?status=${params.status}` : "/tickets";
  const tickets = await apiRequest<Ticket[]>(path);

  return (
    <div className="space-y-8">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Tickets</h2>
          <p className="text-sm text-slate-500">
            Casos donde el agente no supo o no tuvo certeza.
          </p>
        </div>
        <div className="flex gap-2">
          {["", "open", "in_progress", "resolved"].map((status) => (
            <a
              key={status || "all"}
              href={status ? `?status=${status}` : "?"}
              className="btn-secondary text-xs"
            >
              {status || "todos"}
            </a>
          ))}
        </div>
      </header>

      <table className="table-default">
        <thead>
          <tr>
            <th>Tipo</th>
            <th>Estado</th>
            <th>Resumen</th>
            <th>Creado</th>
            <th />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {tickets.map((ticket) => (
            <tr key={ticket.id}>
              <td>{ticket.type}</td>
              <td>
                <span
                  className={`rounded-md px-2 py-1 text-xs font-medium uppercase ${
                    ticket.status === "open"
                      ? "bg-amber-100 text-amber-800"
                      : ticket.status === "resolved"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-slate-100 text-slate-700"
                  }`}
                >
                  {ticket.status}
                </span>
              </td>
              <td className="max-w-md truncate">{ticket.summary}</td>
              <td>{new Date(ticket.created_at).toLocaleString()}</td>
              <td>
                <ActionFeedbackForm action={updateTicketAction} successMessage="Ticket actualizado.">
                  <div className="flex flex-wrap gap-2">
                    <input type="hidden" name="id" value={ticket.id} />
                    <select name="status" defaultValue={ticket.status} className="form-input max-w-[9rem] py-1 text-xs">
                      <option value="open">open</option>
                      <option value="in_progress">in_progress</option>
                      <option value="resolved">resolved</option>
                      <option value="wont_fix">wont_fix</option>
                    </select>
                    <SubmitButton
                      label="Actualizar"
                      pendingLabel="Guardando…"
                      variant="secondary"
                      className="px-2 py-1 text-xs"
                    />
                  </div>
                </ActionFeedbackForm>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
