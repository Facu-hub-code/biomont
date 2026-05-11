import { revalidatePath } from "next/cache";

import { apiRequest } from "@/lib/api";

type Rtc = {
  id: string;
  phone_e164: string;
  name: string;
  enabled: boolean;
  country_isos: string[];
  created_at: string;
};

async function createRtcAction(formData: FormData) {
  "use server";
  const payload = {
    phone_e164: String(formData.get("phone_e164") ?? "").trim(),
    name: String(formData.get("name") ?? "").trim(),
    enabled: formData.get("enabled") === "on",
    country_isos: String(formData.get("country_isos") ?? "")
      .split(",")
      .map((c) => c.trim().toUpperCase())
      .filter(Boolean),
  };
  await apiRequest("/rtcs", { method: "POST", json: payload });
  revalidatePath("/rtcs");
}

async function deleteRtcAction(formData: FormData) {
  "use server";
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  await apiRequest(`/rtcs/${id}`, { method: "DELETE" });
  revalidatePath("/rtcs");
}

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

      <form action={createRtcAction} className="card grid grid-cols-1 gap-4 md:grid-cols-4">
        <div>
          <label className="form-label" htmlFor="phone_e164">Telefono (E.164)</label>
          <input id="phone_e164" name="phone_e164" required className="form-input" placeholder="+51999..." />
        </div>
        <div>
          <label className="form-label" htmlFor="name">Nombre</label>
          <input id="name" name="name" required className="form-input" />
        </div>
        <div>
          <label className="form-label" htmlFor="country_isos">Paises (CSV iso2)</label>
          <input id="country_isos" name="country_isos" className="form-input" placeholder="PE,EC" />
        </div>
        <div className="flex items-end gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" name="enabled" defaultChecked /> Habilitado
          </label>
          <button type="submit" className="btn-primary">Crear</button>
        </div>
      </form>

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
                <form action={deleteRtcAction}>
                  <input type="hidden" name="id" value={rtc.id} />
                  <button type="submit" className="text-red-600 hover:underline">
                    Eliminar
                  </button>
                </form>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
