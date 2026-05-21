import { Phone } from "lucide-react";

import { ActionFeedbackForm } from "@/components/action-feedback-form";
import { SubmitButton } from "@/components/submit-button";
import { apiRequest } from "@/lib/api";

import { createRtcAction, deleteRtcAction } from "./actions";

type Rtc = {
  id: string;
  phone_e164: string;
  name: string;
  enabled: boolean;
  country_isos: string[];
  created_at: string;
};

export default async function RtcsPage() {
  const rtcs = await apiRequest<Rtc[]>("/rtcs");
  return (
    <div className="space-y-10">
      <header className="page-header">
        <h2 className="page-title">RTCs</h2>
        <p className="page-subtitle">
          Teléfonos autorizados para hablar con el agente por WhatsApp y límites por país de catálogo.
        </p>
      </header>

      <ActionFeedbackForm action={createRtcAction} successMessage="RTC creado.">
        <div className="card-static grid grid-cols-1 gap-5 md:grid-cols-4">
          <div>
            <label className="form-label" htmlFor="phone_e164">
              Teléfono (E.164)
            </label>
            <input
              id="phone_e164"
              name="phone_e164"
              required
              className="form-input font-mono text-sm"
              placeholder="+51999..."
            />
          </div>
          <div>
            <label className="form-label" htmlFor="name">
              Nombre
            </label>
            <input id="name" name="name" required className="form-input" />
          </div>
          <div>
            <label className="form-label" htmlFor="country_isos">
              Países (CSV iso2)
            </label>
            <input id="country_isos" name="country_isos" className="form-input font-mono text-sm" placeholder="PE,EC" />
          </div>
          <div className="flex flex-col justify-end gap-3 md:flex-row md:items-end">
            <label className="flex items-center gap-2 rounded-xl border border-zinc-200/90 bg-white px-4 py-3 text-sm font-medium text-zinc-700 shadow-sm">
              <input type="checkbox" name="enabled" defaultChecked className="rounded border-zinc-300 text-teal-600" />{" "}
              Habilitado
            </label>
            <SubmitButton label="Crear RTC" pendingLabel="Creando…" />
          </div>
        </div>
      </ActionFeedbackForm>

      <ul className="grid gap-4 lg:grid-cols-2">
        {rtcs.map((rtc) => (
          <li key={rtc.id} className="card-static flex flex-col gap-4 border-white/90 p-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex min-w-0 flex-1 gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-teal-500/[0.12] text-teal-800 ring-1 ring-teal-600/15">
                <Phone className="h-5 w-5" aria-hidden />
              </div>
              <div className="min-w-0">
                <p className="text-lg font-semibold tracking-tight text-zinc-900">{rtc.name}</p>
                <p className="mt-1 font-mono text-sm text-zinc-600">{rtc.phone_e164}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span
                    className={`badge rounded-lg px-3 py-1 text-[11px] font-bold uppercase tracking-wide ring-1 ${
                      rtc.enabled
                        ? "border-emerald-200 bg-emerald-50 text-emerald-900 ring-emerald-400/15"
                        : "border-zinc-200 bg-zinc-100 text-zinc-700 ring-zinc-300/15"
                    }`}
                  >
                    {rtc.enabled ? "Activo" : "Inactivo"}
                  </span>
                  <span className="badge-neutral font-mono text-[11px]">
                    {rtc.country_isos.join(", ") || "GLOBAL"}
                  </span>
                </div>
                <p className="mt-3 text-xs font-medium uppercase tracking-wide text-zinc-400">
                  Alta {new Date(rtc.created_at).toLocaleString()}
                </p>
              </div>
            </div>
            <ActionFeedbackForm action={deleteRtcAction} successMessage="RTC eliminado.">
              <input type="hidden" name="id" value={rtc.id} />
              <SubmitButton
                label="Eliminar"
                pendingLabel="Eliminando…"
                variant="dangerLink"
                className="inline-flex items-center gap-2 rounded-xl border border-red-100 bg-red-50 px-4 py-2 text-red-700 hover:bg-red-100"
              />
            </ActionFeedbackForm>
          </li>
        ))}
      </ul>

      {rtcs.length === 0 ? (
        <div className="rounded-[28px] border border-dashed border-zinc-300/90 bg-white/70 px-8 py-16 text-center backdrop-blur-sm">
          <Phone className="mx-auto mb-4 h-10 w-10 text-zinc-300" aria-hidden />
          <p className="text-sm font-semibold text-zinc-700">Sin RTCs configurados</p>
          <p className="mt-2 text-sm text-zinc-500">Creá uno para enlazar WhatsApp Business.</p>
        </div>
      ) : null}
    </div>
  );
}
