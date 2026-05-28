import { ActionFeedbackForm } from "@/components/action-feedback-form";
import { CollapsibleCatalogForm } from "@/components/collapsible-catalog-form";
import { ProductsCatalogView } from "@/components/products-catalog-view";
import { SubmitButton } from "@/components/submit-button";
import { apiRequest } from "@/lib/api";
import { requireRole } from "@/lib/auth";

import { createProductAction } from "./actions";

type ProductListResponse = {
  items: import("@/components/products-catalog-view").CatalogProduct[];
  page: number;
  page_size: number;
  total: number;
};

export default async function ProductsPage() {
  const user = await requireRole(["admin", "scientist", "viewer"]);
  const canMutate = user.role === "admin" || user.role === "scientist";
  const products = await apiRequest<ProductListResponse>("/products?page=1&page_size=100");

  return (
    <div className="space-y-10">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="page-header">
          <h2 className="page-title">Productos</h2>
          <p className="page-subtitle">
            Catálogo, aliases y vínculos con documentos que usa el agente para retrieval contextual.
          </p>
        </div>
      </header>

      {canMutate ? (
        <CollapsibleCatalogForm title="Nuevo producto">
          <ActionFeedbackForm action={createProductAction} successMessage="Producto creado correctamente.">
            <div className="card-static grid grid-cols-1 gap-5 md:grid-cols-3">
              <div>
                <label className="form-label" htmlFor="name">
                  Nombre
                </label>
                <input id="name" name="name" required className="form-input" />
              </div>
              <div>
                <label className="form-label" htmlFor="brand">
                  Marca
                </label>
                <input id="brand" name="brand" defaultValue="Biomont" className="form-input" />
              </div>
              <div>
                <label className="form-label" htmlFor="country_iso">
                  País ISO2
                </label>
                <input id="country_iso" name="country_iso" maxLength={2} className="form-input uppercase" />
              </div>
              <div className="md:col-span-3">
                <SubmitButton label="Crear producto" pendingLabel="Creando…" />
              </div>
            </div>
          </ActionFeedbackForm>
        </CollapsibleCatalogForm>
      ) : null}

      {products.total > products.items.length ? (
        <p className="text-xs font-medium text-zinc-500">
          Mostrando los primeros {products.items.length} de {products.total} productos.
        </p>
      ) : null}

      <ProductsCatalogView products={products.items} />
    </div>
  );
}
