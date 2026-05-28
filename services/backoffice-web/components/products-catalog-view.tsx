"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { ChevronRight, Package, Search } from "lucide-react";

import { matchesSearch } from "@/lib/normalize-search";

export type CatalogProduct = {
  id: string;
  name: string;
  brand: string;
  duration_type: string | null;
  country_iso: string | null;
  alias_count: number;
  document_count: number;
};

type Props = {
  products: CatalogProduct[];
};

export function ProductsCatalogView({ products }: Props) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    return products.filter((p) => {
      const blob = [p.name, p.brand, p.country_iso ?? "GLOBAL", p.duration_type ?? ""].join(
        " ",
      );
      return matchesSearch(blob, query);
    });
  }, [products, query]);

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
          placeholder="Buscar por nombre, marca o país…"
          className="form-input w-full pl-11"
          aria-label="Buscar productos"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {filtered.map((product) => (
          <Link
            key={product.id}
            href={`/products/${product.id}`}
            className="group card-static flex flex-col gap-4 border-white/90 p-6 transition-all duration-300 hover:border-teal-300/45 hover:shadow-lift"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-teal-500/[0.12] text-teal-800 ring-1 ring-teal-600/15">
                <Package className="h-5 w-5" aria-hidden />
              </div>
              <ChevronRight className="h-5 w-5 shrink-0 text-zinc-300 transition group-hover:translate-x-0.5 group-hover:text-teal-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold tracking-tight text-zinc-900">{product.name}</h3>
              <p className="mt-1 text-sm text-zinc-500">{product.brand}</p>
            </div>
            <dl className="grid grid-cols-2 gap-3 border-t border-zinc-100/90 pt-4 text-xs font-medium">
              <div className="rounded-xl bg-zinc-50/95 px-3 py-2 ring-1 ring-zinc-100">
                <dt className="text-zinc-400">País</dt>
                <dd className="mt-0.5 tabular-nums text-zinc-800">{product.country_iso ?? "GLOBAL"}</dd>
              </div>
              <div className="rounded-xl bg-zinc-50/95 px-3 py-2 ring-1 ring-zinc-100">
                <dt className="text-zinc-400">Aliases</dt>
                <dd className="mt-0.5 tabular-nums text-zinc-800">{product.alias_count}</dd>
              </div>
              <div className="col-span-2 rounded-xl bg-gradient-to-r from-teal-50/80 to-white px-3 py-2 ring-1 ring-teal-900/[0.06]">
                <dt className="text-teal-700/80">Documentos enlazados</dt>
                <dd className="mt-0.5 text-lg font-semibold tabular-nums text-teal-900">
                  {product.document_count}
                </dd>
              </div>
            </dl>
          </Link>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-[28px] border border-dashed border-zinc-300/90 bg-white/70 px-8 py-16 text-center backdrop-blur-sm">
          <p className="text-sm font-semibold text-zinc-700">
            {products.length === 0
              ? "Sin productos en catálogo"
              : "Ningún producto coincide con la búsqueda"}
          </p>
          <p className="mt-2 text-sm text-zinc-500">
            {products.length === 0
              ? "Creá el primero para empezar a asociar documentos."
              : "Probá con otro término."}
          </p>
        </div>
      ) : null}
    </div>
  );
}
