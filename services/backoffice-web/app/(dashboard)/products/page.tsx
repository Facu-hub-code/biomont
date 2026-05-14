import Link from "next/link";
import { revalidatePath } from "next/cache";

import { apiRequest } from "@/lib/api";
import { requireRole } from "@/lib/auth";

type Product = {
  id: string;
  name: string;
  brand: string;
  duration_type: string | null;
  country_iso: string | null;
  alias_count: number;
  document_count: number;
};

type ProductListResponse = {
  items: Product[];
  page: number;
  page_size: number;
  total: number;
};

async function createProductAction(formData: FormData) {
  "use server";
  await requireRole(["admin", "scientist"]);
  const payload = {
    name: String(formData.get("name") ?? "").trim(),
    brand: String(formData.get("brand") ?? "Biomont").trim() || "Biomont",
    duration_type: String(formData.get("duration_type") ?? "").trim() || null,
    description: String(formData.get("description") ?? "").trim() || null,
    country_iso: String(formData.get("country_iso") ?? "").trim().toUpperCase() || null,
  };
  await apiRequest("/products", { method: "POST", json: payload });
  revalidatePath("/products");
}

export default async function ProductsPage() {
  const user = await requireRole(["admin", "scientist", "viewer"]);
  const canMutate = user.role === "admin" || user.role === "scientist";
  const products = await apiRequest<ProductListResponse>("/products?page=1&page_size=100");

  return (
    <div className="space-y-8">
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">Productos</h2>
        <p className="text-sm text-slate-500">
          Catalogo de productos y aliases para ingestion y auditoria del agente.
        </p>
      </header>

      {canMutate ? (
        <form action={createProductAction} className="card grid grid-cols-1 gap-4 md:grid-cols-3">
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
              Pais ISO2
            </label>
            <input id="country_iso" name="country_iso" maxLength={2} className="form-input uppercase" />
          </div>
          <div>
            <label className="form-label" htmlFor="duration_type">
              Tipo de duracion
            </label>
            <input id="duration_type" name="duration_type" className="form-input" />
          </div>
          <div className="md:col-span-2">
            <label className="form-label" htmlFor="description">
              Descripcion
            </label>
            <input id="description" name="description" className="form-input" />
          </div>
          <div className="md:col-span-3">
            <button type="submit" className="btn-primary">
              Crear producto
            </button>
          </div>
        </form>
      ) : null}

      <table className="table-default">
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Marca</th>
            <th>Pais</th>
            <th>Aliases</th>
            <th>Documentos</th>
            <th />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {products.items.map((product) => (
            <tr key={product.id}>
              <td className="font-medium">{product.name}</td>
              <td>{product.brand}</td>
              <td>{product.country_iso ?? "GLOBAL"}</td>
              <td>{product.alias_count}</td>
              <td>{product.document_count}</td>
              <td>
                <Link href={`/products/${product.id}`} className="text-biomont-primary hover:underline">
                  Ver detalle
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
