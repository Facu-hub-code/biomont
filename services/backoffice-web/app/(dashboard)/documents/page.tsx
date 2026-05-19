import Link from "next/link";

import { DocumentUploadForm } from "@/components/document-upload-form";
import type { CatalogProduct } from "@/components/product-picker";
import { apiRequest } from "@/lib/api";

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

type ProductListResponse = {
  items: CatalogProduct[];
};

export default async function DocumentsPage() {
  const raw = await apiRequest<Document[]>("/documents");
  if (!Array.isArray(raw)) {
    throw new Error("El API devolvió un formato inesperado al listar documentos.");
  }
  const documents = raw;

  let products: CatalogProduct[] = [];
  try {
    const productList = await apiRequest<ProductListResponse>("/products?page=1&page_size=100");
    products = productList.items;
  } catch {
    products = [];
  }

  return (
    <div className="space-y-8">
      <header className="page-header">
        <h2 className="page-title">Documentos</h2>
        <p className="page-subtitle">
          Subi un PDF y lo procesamos con docling para alimentar el RAG.
        </p>
      </header>

      <DocumentUploadForm products={products} />

      <div className="table-shell overflow-x-auto">
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
                <td className="font-medium text-slate-900">{doc.title}</td>
                <td className="max-w-xs text-sm">{formatLinkedProducts(doc)}</td>
                <td>{doc.country_iso ?? "GLOBAL"}</td>
                <td>
                  <span className="badge-neutral uppercase">{doc.status}</span>
                </td>
                <td>{doc.chunk_count}</td>
                <td className="text-slate-600">{new Date(doc.updated_at).toLocaleString()}</td>
                <td>
                  <Link
                    href={`/documents/${doc.id}`}
                    className="text-sm font-medium text-biomont-primary hover:underline"
                  >
                    Ver detalle
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
