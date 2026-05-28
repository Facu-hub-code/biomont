"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { ChevronRight, FileText, Search } from "lucide-react";

import type { CatalogProduct } from "@/components/products-catalog-view";
import { matchesSearch } from "@/lib/normalize-search";

type LinkedProduct = {
  product_id: string;
  name: string;
  is_primary: boolean;
};

export type CatalogDocument = {
  id: string;
  title: string;
  product_name: string | null;
  linked_products: LinkedProduct[];
  country_iso: string | null;
  status: string;
  kind: string;
  chunk_count: number;
  updated_at: string;
};

const DOCUMENT_KIND_LABELS: Record<string, string> = {
  ficha_tecnica: "Ficha técnica",
  bitacora: "Bitácora",
  balotario: "Balotario",
};

function formatDocumentKind(kind: string): string {
  return DOCUMENT_KIND_LABELS[kind] ?? kind;
}

function formatLinkedProducts(doc: CatalogDocument): string {
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

function docMatchesProduct(doc: CatalogDocument, productId: string | null): boolean {
  if (!productId) return true;
  return doc.linked_products?.some((p) => p.product_id === productId) ?? false;
}

type Props = {
  documents: CatalogDocument[];
  products: CatalogProduct[];
};

export function DocumentsCatalogView({ documents, products }: Props) {
  const [query, setQuery] = useState("");
  const [productFilter, setProductFilter] = useState<string | null>(null);

  const filtered = useMemo(() => {
    return documents.filter((doc) => {
      if (!docMatchesProduct(doc, productFilter)) return false;
      const blob = [doc.title, formatLinkedProducts(doc), doc.status, doc.kind].join(" ");
      return matchesSearch(blob, query);
    });
  }, [documents, query, productFilter]);

  return (
    <div className="space-y-6">
      <div className="relative max-w-xl">
        <Search
          className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400"
          aria-hidden
        />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar por título o producto…"
          className="form-input w-full pl-11"
          aria-label="Buscar documentos"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setProductFilter(null)}
          className={`filter-chip ${productFilter === null ? "filter-chip-active" : ""}`}
        >
          Todos
        </button>
        {products.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => setProductFilter(p.id)}
            className={`filter-chip ${productFilter === p.id ? "filter-chip-active" : ""}`}
          >
            {p.name}
          </button>
        ))}
      </div>

      <div className="grid gap-4">
        {filtered.map((doc) => (
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

      {filtered.length === 0 ? (
        <div className="rounded-[28px] border border-dashed border-zinc-300/90 bg-white/70 px-8 py-16 text-center backdrop-blur-sm">
          <p className="text-sm font-semibold text-zinc-700">
            {documents.length === 0
              ? "Todavía no hay documentos"
              : "Ningún documento coincide con los filtros"}
          </p>
          <p className="mt-2 text-sm text-zinc-500">
            {documents.length === 0
              ? "Subí el primer PDF para iniciar la ingesta."
              : "Probá otro término o producto."}
          </p>
        </div>
      ) : null}
    </div>
  );
}
