import Link from "next/link";

import { ChevronRight, Package } from "lucide-react";

import { ActionFeedbackForm } from "@/components/action-feedback-form";
import { SubmitButton } from "@/components/submit-button";
import { apiRequest } from "@/lib/api";
import { requireRole } from "@/lib/auth";

import { createProductAction } from "./actions";

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

export default async function ProductsPage() {
  const user = await requireRole(["admin", "scientist", "viewer"]);
  const canMutate = user.role === "admin" || user.role === "scientist";
  const products = await apiRequest<ProductListResponse>("/products?page=1&page_size=100");

  return (
    <div className="space-y-10">
      <header className="page-header">
        <h2 className="page-title">Productos</h2>
        <p className="page-subtitle">
          Catálogo, aliases y vínculos con documentos que usa el agente para retrieval contextual.
        </p>
      </header>

      {canMutate ? (
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
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {products.items.map((product) => (
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
                <dd className="mt-0.5 text-lg font-semibold tabular-nums text-teal-900">{product.document_count}</dd>
              </div>
            </dl>
          </Link>
        ))}
      </div>

      {products.items.length === 0 ? (
        <div className="rounded-[28px] border border-dashed border-zinc-300/90 bg-white/70 px-8 py-16 text-center backdrop-blur-sm">
          <p className="text-sm font-semibold text-zinc-700">Sin productos en catálogo</p>
          <p className="mt-2 text-sm text-zinc-500">Creá el primero para empezar a asociar documentos.</p>
        </div>
      ) : null}
    </div>
  );
}
