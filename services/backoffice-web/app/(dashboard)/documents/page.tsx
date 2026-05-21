import Link from "next/link";
import { Suspense } from "react";

import { ChevronRight, FileText } from "lucide-react";

import { DocumentsDeletedToast } from "@/components/documents-deleted-toast";
import { DocumentUploadForm } from "@/components/document-upload-form";
import type { CatalogProduct } from "@/components/product-picker";
import { apiRequest } from "@/lib/api";

type LinkedProduct = {
  product_id: string;
  name: string;
  is_primary: boolean;
};

type DocumentKind = "ficha_tecnica" | "bitacora" | "balotario";

type Document = {
  id: string;
  title: string;
  product_name: string | null;
  linked_products: LinkedProduct[];
  country_iso: string | null;
  status: string;
  kind: DocumentKind;
  chunk_count: number;
  updated_at: string;
};

const DOCUMENT_KIND_LABELS: Record<DocumentKind, string> = {
  ficha_tecnica: "Ficha técnica",
  bitacora: "Bitácora",
  balotario: "Balotario",
};

function formatDocumentKind(kind: string): string {
  if (kind in DOCUMENT_KIND_LABELS) {
    return DOCUMENT_KIND_LABELS[kind as DocumentKind];
  }
  return kind;
}

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

      <DocumentUploadForm products={products} />

      <div className="grid gap-4">
        {documents.map((doc) => (
          <Link
            key={doc.id}
            href={`/documents/${doc.id}`}
            className="group card-static flex flex-col gap-4 border-white/90 p-6 transition-all duration-300 hover:border-teal-300/45 hover:shadow-lift lg:flex-row lg:items-start lg:justify-between"
          >
            <div className="flex min-w-0 flex-1 gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-zinc-800 to-zinc-950 text-white shadow-lg ring-2 ring-white">
                <FileText className="h-6 w-6 opacity-95" aria-hidden />
              </div>
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-lg font-semibold tracking-tight text-zinc-900">{doc.title}</h3>
                  <span className="badge-neutral">{formatDocumentKind(doc.kind ?? "bitacora")}</span>
                  <span className="badge-neutral font-mono uppercase">{doc.status}</span>
                </div>
                <p className="text-sm leading-relaxed text-zinc-600">{formatLinkedProducts(doc)}</p>
                <div className="flex flex-wrap gap-4 text-xs font-medium text-zinc-500">
                  <span>
                    País: <span className="text-zinc-800">{doc.country_iso ?? "GLOBAL"}</span>
                  </span>
                  <span className="tabular-nums">
                    Chunks: <span className="text-zinc-800">{doc.chunk_count}</span>
                  </span>
                  <span className="tabular-nums">
                    Actualizado:{" "}
                    <span className="text-zinc-800">{new Date(doc.updated_at).toLocaleString()}</span>
                  </span>
                </div>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2 self-start lg:flex-col lg:items-end">
              <span className="text-sm font-semibold text-teal-700 transition group-hover:text-teal-800">
                Abrir detalle
              </span>
              <ChevronRight className="h-5 w-5 text-zinc-300 transition group-hover:translate-x-0.5 group-hover:text-teal-600" />
            </div>
          </Link>
        ))}
      </div>

      {documents.length === 0 ? (
        <div className="rounded-[28px] border border-dashed border-zinc-300/90 bg-white/70 px-8 py-16 text-center backdrop-blur-sm">
          <p className="text-sm font-semibold text-zinc-700">Todavía no hay documentos</p>
          <p className="mt-2 text-sm text-zinc-500">Subí el primer PDF para iniciar la ingesta.</p>
        </div>
      ) : null}
    </div>
  );
}
