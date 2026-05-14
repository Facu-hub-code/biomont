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
    <div className="space-y-8">
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">RTCs</h2>
        <p className="text-sm text-slate-500">
          Telefonos habilitados para consultar al agente por WhatsApp.
        </p>
      </header>

      <ActionFeedbackForm action={createRtcAction} successMessage="RTC creado.">
        <div className="card grid grid-cols-1 gap-4 md:grid-cols-4">
          <div>
            <label className="form-label" htmlFor="phone_e164">
              Telefono (E.164)
            </label>
            <input
              id="phone_e164"
              name="phone_e164"
              required
              className="form-input"
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
              Paises (CSV iso2)
            </label>
            <input id="country_isos" name="country_isos" className="form-input" placeholder="PE,EC" />
          </div>
          <div className="flex items-end gap-3">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" name="enabled" defaultChecked /> Habilitado
            </label>
            <SubmitButton label="Crear" pendingLabel="Creando…" />
          </div>
        </div>
      </ActionFeedbackForm>

      <table className="table-default">
        <thead>
          <tr>
            <th>Telefono</th>
            <th>Nombre</th>
            <th>Paises</th>
            <th>Habilitado</th>
            <th>Creado</th>
            <th />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {rtcs.map((rtc) => (
            <tr key={rtc.id}>
              <td className="font-mono">{rtc.phone_e164}</td>
              <td>{rtc.name}</td>
              <td>{rtc.country_isos.join(", ") || "-"}</td>
              <td>{rtc.enabled ? "si" : "no"}</td>
              <td>{new Date(rtc.created_at).toLocaleString()}</td>
              <td>
                <ActionFeedbackForm action={deleteRtcAction} successMessage="RTC eliminado.">
                  <input type="hidden" name="id" value={rtc.id} />
                  <SubmitButton label="Eliminar" pendingLabel="Eliminando…" variant="dangerLink" />
                </ActionFeedbackForm>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
