import { ActionFeedbackForm } from "@/components/action-feedback-form";
import { SubmitButton } from "@/components/submit-button";
import { apiRequest } from "@/lib/api";
import { requireRole } from "@/lib/auth";

import { createCompetitorAction } from "./actions";

type CompetitorListResponse = {
  items: Array<{
    id: string;
    name: string;
    brand: string | null;
    is_internal: boolean;
  }>;
  total: number;
};

export default async function CompetitorsPage() {
  const user = await requireRole(["admin", "scientist", "viewer"]);
  const canMutate = user.role === "admin" || user.role === "scientist";
  const data = await apiRequest<CompetitorListResponse>("/competitors?page=1&page_size=100");

  return (
    <div className="space-y-8">
      <header className="page-header">
        <h2 className="page-title">Competidores</h2>
        <p className="page-subtitle">
          Catálogo de marcas usadas en cuadros comparativos comerciales.
        </p>
      </header>

      {canMutate ? (
        <section className="card space-y-4">
          <h3 className="text-lg font-semibold text-slate-900">Nuevo competidor</h3>
          <ActionFeedbackForm action={createCompetitorAction} successMessage="Competidor creado.">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div>
                <label className="form-label" htmlFor="name">Nombre</label>
                <input id="name" name="name" required className="form-input" />
              </div>
              <div>
                <label className="form-label" htmlFor="brand">Marca</label>
                <input id="brand" name="brand" className="form-input" />
              </div>
              <div className="flex items-end gap-2">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="is_internal" className="h-4 w-4" />
                  Producto Biomont interno
                </label>
              </div>
              <div className="md:col-span-3">
                <SubmitButton label="Crear" pendingLabel="Creando…" />
              </div>
            </div>
          </ActionFeedbackForm>
        </section>
      ) : null}

      <section className="card">
        <table className="table-default">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Marca</th>
              <th>Interno</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((c) => (
              <tr key={c.id}>
                <td className="font-medium">{c.name}</td>
                <td>{c.brand ?? "—"}</td>
                <td>{c.is_internal ? "Sí" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.items.length === 0 ? (
          <p className="p-4 text-sm text-slate-500">Sin competidores registrados.</p>
        ) : null}
      </section>
    </div>
  );
}
