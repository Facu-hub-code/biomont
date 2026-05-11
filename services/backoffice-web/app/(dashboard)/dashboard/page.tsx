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
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">Dashboard</h2>
        <p className="text-sm text-slate-500">
          Resumen de actividad del agente y gaps de informacion.
        </p>
      </header>

      {error ? (
        <div className="card border-red-200 bg-red-50 text-red-700">
          No se pudo cargar el resumen: {error}
        </div>
      ) : null}

      {data ? (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <Stat label="Conversaciones" value={data.total_conversations} />
            <Stat label="Mensajes usuarios" value={data.total_messages} />
            <Stat label="Respuestas con cita" value={data.total_answered} />
            <Stat label="Sin info (gaps)" value={data.total_no_match} highlight />
          </div>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <Card title="Uso por pais">
              <ul className="space-y-1 text-sm">
                {data.by_country.length === 0 ? (
                  <li className="text-slate-500">Sin datos</li>
                ) : (
                  data.by_country.map((row, idx) => (
                    <li key={idx} className="flex justify-between">
                      <span>{row.country_iso ?? "GLOBAL"}</span>
                      <span className="font-medium">{row.total}</span>
                    </li>
                  ))
                )}
              </ul>
            </Card>
            <Card title="Top productos consultados">
              <ul className="space-y-1 text-sm">
                {data.top_products.length === 0 ? (
                  <li className="text-slate-500">Sin datos</li>
                ) : (
                  data.top_products.map((row, idx) => (
                    <li key={idx} className="flex justify-between">
                      <span>{row.product_name}</span>
                      <span className="font-medium">{row.total}</span>
                    </li>
                  ))
                )}
              </ul>
            </Card>
          </div>
          <Card title="Latencia">
            <p className="text-sm text-slate-700">
              Latencia media de respuesta del agente:{" "}
              <span className="font-semibold">{data.avg_latency_ms.toFixed(0)} ms</span>
            </p>
          </Card>
        </>
      ) : null}
    </div>
  );
}

function Stat({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div className="card">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p
        className={`mt-2 text-3xl font-semibold ${
          highlight ? "text-biomont-accent" : "text-slate-900"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <h3 className="mb-3 text-sm font-semibold text-slate-700">{title}</h3>
      {children}
    </div>
  );
}
