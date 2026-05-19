import Link from "next/link";

import { ActionFeedbackForm } from "@/components/action-feedback-form";
import { SubmitButton } from "@/components/submit-button";
import { apiRequest } from "@/lib/api";

import { uploadDocumentAction } from "./actions";

type LinkedProduct = {
  product_id: string;
  name: string;
  is_primary: boolean;
};

type Document = {
  id: string;
  title: string;
  product_name: string | null;
  linked_products: LinkedProduct[];
  country_iso: string | null;
  status: string;
  chunk_count: number;
  updated_at: string;
};

function formatLinkedProducts(doc: Document): string {
  if (doc.linked_products?.length) {
    return doc.linked_products
      .map((p) => (p.is_primary ? `${p.name} (primario)` : p.name))
      .join(", ");
  }
  if (doc.product_name?.trim()) {
    return doc.product_name;
  }
  return "-";
}

type ProductItem = {
  id: string;
  name: string;
  country_iso: string | null;
};

type ProductListResponse = {
  items: ProductItem[];
};

export default async function DocumentsPage() {
  const raw = await apiRequest<Document[]>("/documents");
  if (!Array.isArray(raw)) {
    throw new Error("El API devolvió un formato inesperado al listar documentos.");
  }
  const documents = raw;

  let products: ProductItem[] = [];
  try {
    const productList = await apiRequest<ProductListResponse>("/products?page=1&page_size=100");
    products = productList.items;
  } catch {
    products = [];
  }

  return (
    <div className="space-y-8">
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">Documentos</h2>
        <p className="text-sm text-slate-500">
          Subi un PDF y lo procesamos con docling para alimentar el RAG.
        </p>
      </header>

      <ActionFeedbackForm
        action={uploadDocumentAction}
        successMessage="Documento enviado para procesamiento."
      >
        <div className="card grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <label className="form-label" htmlFor="file">
              Archivo PDF
            </label>
            <input
              id="file"
              name="file"
              type="file"
              accept="application/pdf"
              required
              className="form-input"
            />
          </div>
          <div>
            <label className="form-label" htmlFor="title">
              Titulo
            </label>
            <input id="title" name="title" required className="form-input" />
          </div>
          <div className="md:col-span-2">
            <label className="form-label" htmlFor="product_ids">
              Productos del catalogo (puede elegir varios)
            </label>
            <select
              id="product_ids"
              name="product_ids"
              multiple
              size={Math.min(6, Math.max(3, products.length))}
              className="form-input min-h-[8rem]"
            >
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name} {product.country_iso ? `(${product.country_iso})` : "(GLOBAL)"}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-slate-500">
              El primero seleccionado sera el producto primario al ingestar. Cmd/Ctrl+clic para
              varios (ej. Proteggo M y 3M en la misma bitacora).
            </p>
          </div>
          <div>
            <label className="form-label" htmlFor="product_name">
              Producto
            </label>
            <input
              id="product_name"
              name="product_name"
              className="form-input"
              placeholder="Opcional si no elegis del catalogo"
            />
          </div>
          <div>
            <label className="form-label" htmlFor="country_iso">
              Pais (iso2, vacio = global)
            </label>
            <input
              id="country_iso"
              name="country_iso"
              maxLength={2}
              className="form-input uppercase"
            />
          </div>
          <div>
            <label className="form-label" htmlFor="language">
              Idioma
            </label>
            <input id="language" name="language" defaultValue="es" maxLength={2} className="form-input" />
          </div>
          <div>
            <label className="form-label" htmlFor="kind">
              Tipo
            </label>
            <select id="kind" name="kind" defaultValue="bitacora" className="form-input">
              <option value="ficha_tecnica">ficha_tecnica</option>
              <option value="bitacora">bitacora</option>
              <option value="balotario">balotario</option>
            </select>
          </div>
          <div className="md:col-span-2">
            <SubmitButton label="Procesar y validar" pendingLabel="Procesando…" />
          </div>
        </div>
      </ActionFeedbackForm>

      <table className="table-default">
        <thead>
          <tr>
            <th>Titulo</th>
            <th>Productos (catalogo)</th>
            <th>Pais</th>
            <th>Status</th>
            <th>Chunks</th>
            <th>Actualizado</th>
            <th />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {documents.map((doc) => (
            <tr key={doc.id}>
              <td className="font-medium">{doc.title}</td>
              <td className="max-w-xs text-sm">{formatLinkedProducts(doc)}</td>
              <td>{doc.country_iso ?? "GLOBAL"}</td>
              <td>
                <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium uppercase">
                  {doc.status}
                </span>
              </td>
              <td>{doc.chunk_count}</td>
              <td>{new Date(doc.updated_at).toLocaleString()}</td>
              <td>
                <Link href={`/documents/${doc.id}`} className="text-biomont-primary hover:underline">
                  Ver markdown
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
