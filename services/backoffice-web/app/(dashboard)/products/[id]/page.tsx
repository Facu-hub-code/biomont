import { notFound } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiRequest } from "@/lib/api";
import { requireRole } from "@/lib/auth";

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

async function updateProductAction(formData: FormData) {
  "use server";
  const user = await requireRole(["admin", "scientist"]);
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const payload = {
    name: String(formData.get("name") ?? "").trim() || undefined,
    brand: String(formData.get("brand") ?? "").trim() || undefined,
    duration_type: String(formData.get("duration_type") ?? "").trim() || null,
    description: String(formData.get("description") ?? "").trim() || null,
    country_iso: String(formData.get("country_iso") ?? "").trim().toUpperCase() || null,
  };
  await apiRequest(`/products/${id}`, { method: "PATCH", json: payload });
  revalidatePath(`/products/${id}`);
  revalidatePath("/products");
  if (user.role === "admin") return;
}

async function deleteProductAction(formData: FormData) {
  "use server";
  await requireRole(["admin"]);
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  await apiRequest(`/products/${id}`, { method: "DELETE" });
  revalidatePath("/products");
}

async function createAliasAction(formData: FormData) {
  "use server";
  await requireRole(["admin", "scientist"]);
  const productId = String(formData.get("product_id") ?? "");
  const alias = String(formData.get("alias") ?? "").trim();
  if (!productId || !alias) return;
  await apiRequest(`/products/${productId}/aliases`, {
    method: "POST",
    json: {
      alias,
      source: String(formData.get("source") ?? "manual"),
      confidence: Number(formData.get("confidence") ?? 1),
    },
  });
  revalidatePath(`/products/${productId}`);
}

async function updateAliasAction(formData: FormData) {
  "use server";
  await requireRole(["admin", "scientist"]);
  const productId = String(formData.get("product_id") ?? "");
  const aliasId = String(formData.get("alias_id") ?? "");
  const alias = String(formData.get("alias") ?? "").trim();
  if (!productId || !aliasId || !alias) return;
  await apiRequest(`/products/${productId}/aliases/${aliasId}`, {
    method: "PATCH",
    json: {
      alias,
      source: String(formData.get("source") ?? "manual"),
      confidence: Number(formData.get("confidence") ?? 1),
    },
  });
  revalidatePath(`/products/${productId}`);
}

async function deleteAliasAction(formData: FormData) {
  "use server";
  await requireRole(["admin", "scientist"]);
  const productId = String(formData.get("product_id") ?? "");
  const aliasId = String(formData.get("alias_id") ?? "");
  if (!productId || !aliasId) return;
  await apiRequest(`/products/${productId}/aliases/${aliasId}`, { method: "DELETE" });
  revalidatePath(`/products/${productId}`);
}

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
          <form action={updateProductAction} className="grid grid-cols-1 gap-4 md:grid-cols-3">
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
              <button type="submit" className="btn-primary">
                Guardar cambios
              </button>
            </div>
          </form>
          {canDelete ? (
            <form action={deleteProductAction}>
              <input type="hidden" name="id" value={product.id} />
              <button type="submit" className="btn-secondary text-red-700">
                Eliminar producto
              </button>
            </form>
          ) : null}
        </section>
      ) : null}

      <section className="card space-y-4">
        <h3 className="text-lg font-semibold text-slate-900">Aliases</h3>
        {canMutate ? (
          <form action={createAliasAction} className="grid grid-cols-1 gap-4 md:grid-cols-4">
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
              <input id="confidence" name="confidence" type="number" min="0" max="1" step="0.01" defaultValue="1" className="form-input" />
            </div>
            <div className="md:col-span-4">
              <button type="submit" className="btn-primary">
                Agregar alias
              </button>
            </div>
          </form>
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
                  <div className="flex gap-3">
                    <form action={updateAliasAction} className="flex gap-2">
                      <input type="hidden" name="product_id" value={product.id} />
                      <input type="hidden" name="alias_id" value={alias.id} />
                      <input type="hidden" name="source" value={alias.source} />
                      <input type="hidden" name="confidence" value={alias.confidence} />
                      <input name="alias" defaultValue={alias.alias} className="form-input py-1" />
                      <button type="submit" className="text-biomont-primary hover:underline">
                        Guardar
                      </button>
                    </form>
                    <form action={deleteAliasAction}>
                      <input type="hidden" name="product_id" value={product.id} />
                      <input type="hidden" name="alias_id" value={alias.id} />
                      <button type="submit" className="text-red-600 hover:underline">
                        Eliminar
                      </button>
                    </form>
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
