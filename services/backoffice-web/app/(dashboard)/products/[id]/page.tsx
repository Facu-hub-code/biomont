import { notFound } from "next/navigation";

import { ActionFeedbackForm } from "@/components/action-feedback-form";
import { SubmitButton } from "@/components/submit-button";
import { apiRequest } from "@/lib/api";
import { requireRole } from "@/lib/auth";

import Link from "next/link";

import {
  createAliasAction,
  deleteAliasAction,
  deleteProductAction,
  linkDocumentAction,
  unlinkDocumentAction,
  updateAliasAction,
  updateProductAction,
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
  const canDelete = user.role === "admin";

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
  let allDocuments: DocumentSummary[] = [];
  try {
    const raw = await apiRequest<DocumentSummary[]>("/documents");
    allDocuments = Array.isArray(raw) ? raw : [];
  } catch {
    allDocuments = [];
  }

  return (
    <div className="space-y-8">
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
          {canDelete ? (
            <ActionFeedbackForm
              action={deleteProductAction}
              successMessage="Producto eliminado."
              redirectOnSuccess="/products"
            >
              <input type="hidden" name="id" value={product.id} />
              <SubmitButton
                label="Eliminar producto"
                pendingLabel="Eliminando…"
                variant="secondary"
                className="border-red-200 text-red-700 hover:bg-red-50"
              />
            </ActionFeedbackForm>
          ) : null}
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
    </div>
  );
}
