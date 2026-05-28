import { Suspense } from "react";

import { CollapsibleCatalogForm } from "@/components/collapsible-catalog-form";
import { DocumentUploadForm } from "@/components/document-upload-form";
import { DocumentsCatalogView, type CatalogDocument } from "@/components/documents-catalog-view";
import type { CatalogProduct } from "@/components/products-catalog-view";
import { DocumentsDeletedToast } from "@/components/documents-deleted-toast";
import { apiRequest } from "@/lib/api";
import { requireRole } from "@/lib/auth";

type ProductListResponse = {
  items: CatalogProduct[];
};

export default async function DocumentsPage() {
  const user = await requireRole(["admin", "scientist", "viewer"]);
  const canMutate = user.role === "admin" || user.role === "scientist";
  const raw = await apiRequest<CatalogDocument[]>("/documents");
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
    <div className="space-y-10">
      <Suspense fallback={null}>
        <DocumentsDeletedToast />
      </Suspense>
      <header className="page-header">
        <h2 className="page-title">Documentos</h2>
        <p className="page-subtitle">
          Subí un PDF y lo procesamos con Docling para alimentar el RAG del agente con chunks validados.
        </p>
      </header>

      {canMutate ? (
        <CollapsibleCatalogForm title="Subir documento">
          <DocumentUploadForm products={products} />
        </CollapsibleCatalogForm>
      ) : null}

      <DocumentsCatalogView documents={documents} products={products} />
    </div>
  );
}
