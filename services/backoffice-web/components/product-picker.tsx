"use client";

import { useMemo, useState } from "react";

export type CatalogProduct = {
  id: string;
  name: string;
  country_iso: string | null;
};

type Props = {
  products: CatalogProduct[];
  name?: string;
  defaultSelectedIds?: string[];
  hint?: string;
  showPrimaryRadio?: boolean;
  defaultPrimaryId?: string;
};

function normalizeSearch(value: string): string {
  return value.trim().toLowerCase();
}

export function ProductPicker({
  products,
  name = "product_ids",
  defaultSelectedIds = [],
  hint,
  showPrimaryRadio = false,
  defaultPrimaryId = "",
}: Props) {
  const [query, setQuery] = useState("");
  const selectedSet = useMemo(() => new Set(defaultSelectedIds), [defaultSelectedIds]);

  const filtered = useMemo(() => {
    const q = normalizeSearch(query);
    if (!q) return products;
    return products.filter((product) => {
      const label = `${product.name} ${product.country_iso ?? "GLOBAL"}`.toLowerCase();
      return label.includes(q);
    });
  }, [products, query]);

  return (
    <div className="space-y-3">
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Buscar producto por nombre o país…"
        className="form-input mt-0"
        aria-label="Buscar productos"
      />
      <div className="max-h-56 space-y-1 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50/50 p-2">
        {filtered.length === 0 ? (
          <p className="px-2 py-3 text-sm text-slate-500">No hay productos que coincidan.</p>
        ) : (
          filtered.map((product) => (
            <label
              key={product.id}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-transparent bg-white px-3 py-2 shadow-sm transition-colors hover:border-slate-200"
            >
              <input
                type="checkbox"
                name={name}
                value={product.id}
                defaultChecked={selectedSet.has(product.id)}
                className="h-4 w-4 rounded border-slate-300 text-biomont-primary focus:ring-biomont-primary/30"
              />
              <span className="flex-1 text-sm font-medium text-slate-800">
                {product.name}{" "}
                <span className="font-normal text-slate-500">
                  ({product.country_iso ?? "GLOBAL"})
                </span>
              </span>
              {showPrimaryRadio ? (
                <label className="flex items-center gap-1 text-xs text-slate-600">
                  <input
                    type="radio"
                    name="primary_product_id"
                    value={product.id}
                    defaultChecked={defaultPrimaryId === product.id}
                    className="h-3.5 w-3.5 text-biomont-primary focus:ring-biomont-primary/30"
                  />
                  Primario
                </label>
              ) : null}
            </label>
          ))
        )}
      </div>
      {hint ? <p className="text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}
