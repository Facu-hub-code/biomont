import { notFound } from "next/navigation";

import { ActionFeedbackForm } from "@/components/action-feedback-form";
import { SubmitButton } from "@/components/submit-button";
import { apiRequest } from "@/lib/api";
import { requireRole } from "@/lib/auth";

import { CatalogBackLink } from "@/components/catalog-back-link";
import Link from "next/link";

import {
  createAliasAction,
  createDosingRuleAction,
  deleteAliasAction,
  importComparisonAction,
  linkDocumentAction,
  publishComparisonAction,
  publishDosingAction,
  unlinkDocumentAction,
  updateAliasAction,
  updateProductAction,
  upsertDosingProfileAction,
} from "./actions";

type Product = {
  id: string;
  name: string;
  brand: string;
  duration_type: string | null;
  description: string | null;
  country_iso: string | null;
  alias_count: number;
  document_count: number;
};

type Alias = {
  id: string;
  product_id: string;
  alias: string;
  normalized_alias: string;
  source: string;
  confidence: number;
};

type AliasListResponse = {
  items: Alias[];
};

type LinkedDocument = {
  document_id: string;
  title: string;
  kind: string;
  status: string;
  country_iso: string | null;
  is_primary: boolean;
  updated_at: string;
};

type LinkedDocumentsResponse = {
  items: LinkedDocument[];
  total: number;
};

type DosingBundle = {
  profiles: Array<{
    id: string;
    species: string;
    supports_dose_calculation: boolean;
    completeness_status: string;
    published_version: number;
    min_weight_kg: string | null;
    max_weight_kg: string | null;
  }>;
  draft_rules: Array<{
    id: string;
    profile_id: string;
    rule_type: string;
    label: string | null;
    weight_min_kg: string | null;
    weight_max_kg: string | null;
    output_value: string | null;
    output_unit: string;
    formula_numerator: string | null;
  }>;
  open_gaps_count: number;
};

type ComparisonSet = {
  id: string;
  completeness_status: string;
  published_version: number;
} | null;

type DocumentSummary = {
  id: string;
  title: string;
};

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const user = await requireRole(["admin", "scientist", "viewer"]);
  const canMutate = user.role === "admin" || user.role === "scientist";

  let product: Product;
  try {
    product = await apiRequest<Product>(`/products/${id}`);
  } catch {
    notFound();
  }
  const aliases = await apiRequest<AliasListResponse>(`/products/${id}/aliases?page=1&page_size=100`);
  const linkedDocs = await apiRequest<LinkedDocumentsResponse>(
    `/products/${id}/documents?page=1&page_size=100`,
  );
  let dosing: DosingBundle = { profiles: [], draft_rules: [], open_gaps_count: 0 };
  let comparison: ComparisonSet = null;
  try {
    dosing = await apiRequest<DosingBundle>(`/products/${id}/dosing`);
  } catch {
    dosing = { profiles: [], draft_rules: [], open_gaps_count: 0 };
  }
  try {
    comparison = await apiRequest<ComparisonSet>(`/products/${id}/comparison`);
  } catch {
    comparison = null;
  }
  let allDocuments: DocumentSummary[] = [];
  try {
    const raw = await apiRequest<DocumentSummary[]>("/documents");
    allDocuments = Array.isArray(raw) ? raw : [];
  } catch {
    allDocuments = [];
  }

  return (
    <div className="space-y-8">
      <CatalogBackLink href="/products" label="Volver a productos" />
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">{product.name}</h2>
        <p className="text-sm text-slate-500">
          {product.brand} · {product.country_iso ?? "GLOBAL"} · {product.document_count} documentos
        </p>
      </header>

      {canMutate ? (
        <section className="card space-y-4">
          <ActionFeedbackForm action={updateProductAction} successMessage="Cambios guardados.">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <input type="hidden" name="id" value={product.id} />
              <div>
                <label className="form-label" htmlFor="name">
                  Nombre
                </label>
                <input id="name" name="name" defaultValue={product.name} className="form-input" />
              </div>
              <div>
                <label className="form-label" htmlFor="brand">
                  Marca
                </label>
                <input id="brand" name="brand" defaultValue={product.brand} className="form-input" />
              </div>
              <div>
                <label className="form-label" htmlFor="country_iso">
                  Pais ISO2
                </label>
                <input
                  id="country_iso"
                  name="country_iso"
                  defaultValue={product.country_iso ?? ""}
                  className="form-input uppercase"
                />
              </div>
              <div>
                <label className="form-label" htmlFor="duration_type">
                  Tipo de duracion
                </label>
                <input
                  id="duration_type"
                  name="duration_type"
                  defaultValue={product.duration_type ?? ""}
                  className="form-input"
                />
              </div>
              <div className="md:col-span-2">
                <label className="form-label" htmlFor="description">
                  Descripcion
                </label>
                <input
                  id="description"
                  name="description"
                  defaultValue={product.description ?? ""}
                  className="form-input"
                />
              </div>
              <div className="md:col-span-3">
                <SubmitButton label="Guardar cambios" pendingLabel="Guardando…" />
              </div>
            </div>
          </ActionFeedbackForm>
        </section>
      ) : null}

      <section className="card space-y-4">
        <h3 className="text-lg font-semibold text-slate-900">Documentos vinculados</h3>
        {canMutate ? (
          <ActionFeedbackForm action={linkDocumentAction} successMessage="Documento vinculado.">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
              <input type="hidden" name="product_id" value={product.id} />
              <div className="md:col-span-2">
                <label className="form-label" htmlFor="document_id">
                  Vincular documento
                </label>
                <select id="document_id" name="document_id" required className="form-input">
                  <option value="">Elegir documento…</option>
                  {allDocuments.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.title}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-end gap-2">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="is_primary" className="h-4 w-4" />
                  Marcar como primario
                </label>
              </div>
              <div className="flex items-end">
                <SubmitButton label="Vincular" pendingLabel="Vinculando…" />
              </div>
            </div>
          </ActionFeedbackForm>
        ) : null}
        <table className="table-default">
          <thead>
            <tr>
              <th>Titulo</th>
              <th>Tipo</th>
              <th>Status</th>
              <th>Rol</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {linkedDocs.items.map((doc) => (
              <tr key={doc.document_id}>
                <td className="font-medium">{doc.title}</td>
                <td>{doc.kind}</td>
                <td>{doc.status}</td>
                <td>{doc.is_primary ? "Primario" : "Compartido"}</td>
                <td className="space-x-3">
                  <Link
                    href={`/documents/${doc.document_id}`}
                    className="text-biomont-primary hover:underline"
                  >
                    Ver
                  </Link>
                  {canMutate ? (
                    <ActionFeedbackForm
                      action={unlinkDocumentAction}
                      successMessage="Vinculo eliminado."
                    >
                      <input type="hidden" name="product_id" value={product.id} />
                      <input type="hidden" name="document_id" value={doc.document_id} />
                      <SubmitButton
                        label="Quitar"
                        pendingLabel="Quitando…"
                        variant="dangerLink"
                        className="text-xs"
                      />
                    </ActionFeedbackForm>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {linkedDocs.items.length === 0 ? (
          <p className="text-sm text-slate-500">No hay documentos vinculados a este producto.</p>
        ) : null}
      </section>

      <section className="card space-y-4">
        <h3 className="text-lg font-semibold text-slate-900">Aliases</h3>
        {canMutate ? (
          <ActionFeedbackForm action={createAliasAction} successMessage="Alias agregado.">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
              <input type="hidden" name="product_id" value={product.id} />
              <div className="md:col-span-2">
                <label className="form-label" htmlFor="alias">
                  Alias
                </label>
                <input id="alias" name="alias" required className="form-input" />
              </div>
              <div>
                <label className="form-label" htmlFor="source">
                  Fuente
                </label>
                <input id="source" name="source" defaultValue="manual" className="form-input" />
              </div>
              <div>
                <label className="form-label" htmlFor="confidence">
                  Confianza
                </label>
                <input
                  id="confidence"
                  name="confidence"
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  defaultValue="1"
                  className="form-input"
                />
              </div>
              <div className="md:col-span-4">
                <SubmitButton label="Agregar alias" pendingLabel="Agregando…" />
              </div>
            </div>
          </ActionFeedbackForm>
        ) : null}

        <table className="table-default">
          <thead>
            <tr>
              <th>Alias</th>
              <th>Normalizado</th>
              <th>Fuente</th>
              <th>Confianza</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {aliases.items.map((alias) => (
              <tr key={alias.id}>
                <td>{alias.alias}</td>
                <td className="font-mono text-xs">{alias.normalized_alias}</td>
                <td>{alias.source}</td>
                <td>{alias.confidence}</td>
                <td>
                  {canMutate ? (
                    <div className="flex flex-wrap gap-3">
                      <ActionFeedbackForm action={updateAliasAction} successMessage="Alias actualizado.">
                        <div className="flex flex-wrap items-center gap-2">
                          <input type="hidden" name="product_id" value={product.id} />
                          <input type="hidden" name="alias_id" value={alias.id} />
                          <input type="hidden" name="source" value={alias.source} />
                          <input type="hidden" name="confidence" value={alias.confidence} />
                          <input name="alias" defaultValue={alias.alias} className="form-input max-w-[12rem] py-1 text-sm" />
                          <SubmitButton
                            label="Guardar"
                            pendingLabel="Guardando…"
                            variant="secondary"
                            className="px-3 py-1 text-xs"
                          />
                        </div>
                      </ActionFeedbackForm>
                      <ActionFeedbackForm action={deleteAliasAction} successMessage="Alias eliminado.">
                        <input type="hidden" name="product_id" value={product.id} />
                        <input type="hidden" name="alias_id" value={alias.id} />
                        <SubmitButton
                          label="Eliminar"
                          pendingLabel="Eliminando…"
                          variant="dangerLink"
                          className="text-xs"
                        />
                      </ActionFeedbackForm>
                    </div>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card space-y-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-lg font-semibold text-slate-900">Dosis / presentaciones</h3>
          {dosing.open_gaps_count > 0 ? (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
              Dosis incompleta ({dosing.open_gaps_count} gaps)
            </span>
          ) : null}
        </div>
        {canMutate ? (
          <ActionFeedbackForm action={upsertDosingProfileAction} successMessage="Perfil guardado.">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
              <input type="hidden" name="product_id" value={product.id} />
              <div>
                <label className="form-label" htmlFor="species">Especie</label>
                <input id="species" name="species" placeholder="canine, bovine, calf…" className="form-input" required />
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="supports_dose_calculation" defaultChecked className="h-4 w-4" />
                  Habilitar cálculo
                </label>
              </div>
              <div>
                <label className="form-label" htmlFor="min_weight_kg">Peso min (kg)</label>
                <input id="min_weight_kg" name="min_weight_kg" className="form-input" />
              </div>
              <div>
                <label className="form-label" htmlFor="max_weight_kg_dose">Peso max (kg)</label>
                <input id="max_weight_kg_dose" name="max_weight_kg" className="form-input" />
              </div>
              <div className="md:col-span-4">
                <SubmitButton label="Guardar perfil" pendingLabel="Guardando…" />
              </div>
            </div>
          </ActionFeedbackForm>
        ) : null}
        {dosing.profiles.map((profile) => (
          <div key={profile.id} className="rounded-lg border border-slate-100 p-4">
            <p className="text-sm font-medium">
              {profile.species} · v{profile.published_version} · {profile.completeness_status}
            </p>
            {canMutate ? (
              <ActionFeedbackForm action={createDosingRuleAction} successMessage="Regla agregada." className="mt-3">
                <input type="hidden" name="product_id" value={product.id} />
                <input type="hidden" name="profile_id" value={profile.id} />
                <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
                  <select name="rule_type" className="form-input">
                    <option value="weight_band">Rango peso</option>
                    <option value="formula">Fórmula</option>
                  </select>
                  <input name="label" placeholder="Etiqueta" className="form-input" />
                  <input name="weight_min_kg" placeholder="Peso min" className="form-input" />
                  <input name="weight_max_kg" placeholder="Peso max" className="form-input" />
                  <input name="output_value" placeholder="Valor / mg" className="form-input" />
                  <SubmitButton label="Agregar regla" pendingLabel="…" className="text-xs" />
                </div>
              </ActionFeedbackForm>
            ) : null}
            {canMutate && user.role === "admin" ? (
              <ActionFeedbackForm action={publishDosingAction} successMessage="Publicado." className="mt-2">
                <input type="hidden" name="product_id" value={product.id} />
                <input type="hidden" name="profile_id" value={profile.id} />
                <SubmitButton label="Publicar dosis" pendingLabel="Publicando…" variant="secondary" className="text-xs" />
              </ActionFeedbackForm>
            ) : null}
          </div>
        ))}
        {dosing.draft_rules.length > 0 ? (
          <table className="table-default">
            <thead>
              <tr>
                <th>Tipo</th>
                <th>Etiqueta</th>
                <th>Rango</th>
                <th>Salida</th>
              </tr>
            </thead>
            <tbody>
              {dosing.draft_rules.map((rule) => (
                <tr key={rule.id}>
                  <td>{rule.rule_type}</td>
                  <td>{rule.label ?? "—"}</td>
                  <td>
                    {rule.weight_min_kg != null
                      ? `${rule.weight_min_kg}–${rule.weight_max_kg} kg`
                      : rule.formula_numerator ?? "—"}
                  </td>
                  <td>
                    {rule.output_value} {rule.output_unit}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-slate-500">Sin reglas en borrador.</p>
        )}
      </section>

      <section className="card space-y-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-lg font-semibold text-slate-900">Comparativa comercial</h3>
          {comparison && comparison.completeness_status !== "complete" ? (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
              Comparativa incompleta
            </span>
          ) : null}
        </div>
        {comparison ? (
          <p className="text-sm text-slate-600">
            Set cargado · versión publicada {comparison.published_version} ·{" "}
            {comparison.completeness_status}
          </p>
        ) : (
          <p className="text-sm text-slate-500">Sin cuadro comparativo importado.</p>
        )}
        {canMutate ? (
          <>
            <ActionFeedbackForm action={importComparisonAction} successMessage="Importado.">
              <input type="hidden" name="product_id" value={product.id} />
              <div className="flex flex-wrap items-end gap-3">
                <input
                  name="file"
                  type="file"
                  accept=".xlsx,.xls"
                  required
                  className="form-input max-w-md file:mr-2 file:rounded file:border-0 file:bg-teal-50 file:px-2 file:py-1 file:text-sm"
                />
                <SubmitButton label="Importar Excel" pendingLabel="Importando…" />
              </div>
            </ActionFeedbackForm>
            {user.role === "admin" ? (
              <ActionFeedbackForm action={publishComparisonAction} successMessage="Comparativa publicada.">
                <input type="hidden" name="product_id" value={product.id} />
                <SubmitButton label="Publicar comparativa" pendingLabel="Publicando…" variant="secondary" />
              </ActionFeedbackForm>
            ) : null}
          </>
        ) : null}
      </section>
    </div>
  );
}
