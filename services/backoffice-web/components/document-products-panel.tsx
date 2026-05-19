"use client";

import { ActionFeedbackForm } from "@/components/action-feedback-form";
import { SubmitButton } from "@/components/submit-button";

import { saveDocumentProductsAction } from "@/app/(dashboard)/documents/[id]/actions";

type CatalogProduct = {
  id: string;
  name: string;
  country_iso: string | null;
};

export type LinkedProduct = {
  product_id: string;
  name: string;
  brand?: string;
  is_primary: boolean;
};

export function DocumentProductsPanel({
  documentId,
  catalog,
  linked,
  canMutate,
}: {
  documentId: string;
  catalog: CatalogProduct[];
  linked: LinkedProduct[];
  canMutate: boolean;
}) {
  const linkedIds = new Set(linked.map((p) => p.product_id));
  const defaultPrimary =
    linked.find((p) => p.is_primary)?.product_id ?? linked[0]?.product_id ?? "";

  return (
    <section className="card space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-slate-900">Productos del catalogo</h3>
        <p className="text-sm text-slate-500">
          Un documento puede vincularse a varios productos (ej. bitacora compartida).
          El primario define documents.product_id y los chunks al ingestar; el agente usa
          todos los vinculos para retrieval.
        </p>
      </div>

      {linked.length > 0 ? (
        <ul className="flex flex-wrap gap-2 text-sm">
          {linked.map((p) => (
            <li
              key={p.product_id}
              className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1"
            >
              {p.name}
              {p.is_primary ? (
                <span className="ml-1 text-xs font-medium text-biomont-primary">(primario)</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-500">Sin productos vinculados.</p>
      )}

      {canMutate ? (
        <ActionFeedbackForm
          action={saveDocumentProductsAction}
          successMessage="Vinculos guardados."
        >
          <input type="hidden" name="document_id" value={documentId} />
          <div className="space-y-3">
            {catalog.length === 0 ? (
              <p className="text-sm text-slate-500">No hay productos en el catalogo.</p>
            ) : (
              catalog.map((product) => (
                <label
                  key={product.id}
                  className="flex flex-wrap items-center gap-3 rounded-md border border-slate-100 px-3 py-2"
                >
                  <input
                    type="checkbox"
                    name="product_ids"
                    value={product.id}
                    defaultChecked={linkedIds.has(product.id)}
                    className="h-4 w-4"
                  />
                  <span className="flex-1 text-sm font-medium text-slate-800">
                    {product.name}{" "}
                    <span className="font-normal text-slate-500">
                      {product.country_iso ?? "GLOBAL"}
                    </span>
                  </span>
                  <label className="flex items-center gap-1 text-xs text-slate-600">
                    <input
                      type="radio"
                      name="primary_product_id"
                      value={product.id}
                      defaultChecked={defaultPrimary === product.id}
                    />
                    Primario
                  </label>
                </label>
              ))
            )}
          </div>
          <p className="text-xs text-slate-500">
            Cambiar el primario no re-embeddea chunks; use reingesta si necesita alinear
            metadata de chunks.
          </p>
          <SubmitButton label="Guardar vinculos" pendingLabel="Guardando…" />
        </ActionFeedbackForm>
      ) : null}
    </section>
  );
}
