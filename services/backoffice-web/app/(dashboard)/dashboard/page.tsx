import {
  Globe2,
  MessageSquareText,
  PackageSearch,
  Sparkles,
  Timer,
  TrendingUp,
} from "lucide-react";
import type { ReactNode } from "react";

import { apiRequest } from "@/lib/api";

type Overview = {
  total_conversations: number;
  total_messages: number;
  total_answered: number;
  total_no_match: number;
  avg_latency_ms: number;
  by_country: { country_iso: string | null; total: number }[];
  top_products: { product_name: string; total: number }[];
};

export default async function DashboardPage() {
  let data: Overview | null = null;
  let error: string | null = null;
  try {
    data = await apiRequest<Overview>("/analytics/overview");
  } catch (err) {
    error = err instanceof Error ? err.message : "Error desconocido";
  }

  return (
    <div className="space-y-10">
      <header className="page-header">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 inline-flex items-center gap-2 rounded-full border border-teal-500/15 bg-teal-500/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-teal-800">
              <Sparkles className="h-3.5 w-3.5" aria-hidden />
              Overview en vivo
            </p>
            <h2 className="page-title">Dashboard</h2>
            <p className="page-subtitle">
              Métricas del agente conversacional y huecos donde falta conocimiento validado.
            </p>
          </div>
        </div>
      </header>

      {error ? (
        <div className="rounded-2xl border border-red-200/90 bg-red-50/95 px-5 py-4 text-sm font-medium text-red-900 shadow-soft backdrop-blur-sm">
          No se pudo cargar el resumen: {error}
        </div>
      ) : null}

      {data ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat
              label="Conversaciones"
              value={data.total_conversations}
              icon={<MessageSquareText className="h-5 w-5 text-teal-600" aria-hidden />}
            />
            <Stat
              label="Mensajes de usuarios"
              value={data.total_messages}
              icon={<TrendingUp className="h-5 w-5 text-teal-600" aria-hidden />}
            />
            <Stat
              label="Respuestas con cita"
              value={data.total_answered}
              icon={<Sparkles className="h-5 w-5 text-teal-600" aria-hidden />}
            />
            <Stat
              label="Sin info (gaps)"
              value={data.total_no_match}
              highlight
              icon={<PackageSearch className="h-5 w-5 text-biomont-accent" aria-hidden />}
            />
          </div>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <InsightCard title="Uso por país" icon={<Globe2 className="h-4 w-4" aria-hidden />}>
              <ul className="space-y-3">
                {data.by_country.length === 0 ? (
                  <li className="text-sm text-zinc-500">Sin datos suficientes.</li>
                ) : (
                  data.by_country.map((row, idx) => (
                    <li
                      key={idx}
                      className="flex items-center justify-between rounded-xl bg-zinc-50/90 px-4 py-3 text-sm ring-1 ring-zinc-100"
                    >
                      <span className="font-medium text-zinc-700">
                        {row.country_iso ?? "GLOBAL"}
                      </span>
                      <span className="tabular-nums text-lg font-semibold text-zinc-900">{row.total}</span>
                    </li>
                  ))
                )}
              </ul>
            </InsightCard>
            <InsightCard title="Productos más consultados" icon={<TrendingUp className="h-4 w-4" aria-hidden />}>
              <ul className="space-y-3">
                {data.top_products.length === 0 ? (
                  <li className="text-sm text-zinc-500">Sin datos suficientes.</li>
                ) : (
                  data.top_products.map((row, idx) => (
                    <li
                      key={idx}
                      className="flex items-center justify-between rounded-xl bg-gradient-to-r from-white to-teal-50/40 px-4 py-3 text-sm ring-1 ring-teal-900/[0.06]"
                    >
                      <span className="font-medium text-zinc-800">{row.product_name}</span>
                      <span className="rounded-full bg-white/90 px-3 py-0.5 text-xs font-bold tabular-nums text-teal-800 shadow-sm ring-1 ring-teal-900/10">
                        {row.total}
                      </span>
                    </li>
                  ))
                )}
              </ul>
            </InsightCard>
          </div>
          <div className="card-static flex flex-wrap items-center gap-4 border-teal-500/12 bg-gradient-to-r from-teal-50/50 via-white to-white">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white shadow-soft ring-1 ring-teal-500/15">
              <Timer className="h-6 w-6 text-teal-700" aria-hidden />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-zinc-900">Latencia media del agente</h3>
              <p className="mt-1 text-sm text-zinc-600">
                Tiempo hasta responder con contexto recuperado:{" "}
                <span className="font-semibold tabular-nums text-teal-800">
                  {data.avg_latency_ms.toFixed(0)} ms
                </span>
              </p>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

function Stat({
  label,
  value,
  highlight,
  icon,
}: {
  label: string;
  value: number;
  highlight?: boolean;
  icon: ReactNode;
}) {
  return (
    <div className="card-static group relative overflow-hidden border-white/70 p-5 transition-all duration-300 hover:border-teal-300/35 hover:shadow-lift">
      <div className="pointer-events-none absolute -right-8 -top-8 h-28 w-28 rounded-full bg-gradient-to-br from-teal-400/15 to-transparent blur-2xl transition-opacity duration-500 group-hover:opacity-100" />
      <div className="relative flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">{label}</p>
          <p
            className={`mt-2 text-4xl font-semibold tracking-tight tabular-nums ${
              highlight ? "text-biomont-accent" : "text-zinc-900"
            }`}
          >
            {value}
          </p>
        </div>
        <div className="rounded-2xl bg-teal-500/[0.08] p-2.5 ring-1 ring-teal-600/10">{icon}</div>
      </div>
    </div>
  );
}

function InsightCard({
  title,
  icon,
  children,
}: {
  title: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="card-static border-white/80 p-6">
      <h3 className="mb-5 flex items-center gap-2 text-sm font-semibold text-zinc-800">
        <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-zinc-900 text-white shadow-md">
          {icon}
        </span>
        {title}
      </h3>
      {children}
    </div>
  );
}
