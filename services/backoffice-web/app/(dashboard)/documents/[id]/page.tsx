import { apiRequest } from "@/lib/api";

type DocumentDetail = {
  id: string;
  title: string;
  product_name: string | null;
  country_iso: string | null;
  status: string;
  chunk_count: number;
  markdown: string | null;
};

export default async function DocumentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const doc = await apiRequest<DocumentDetail>(`/documents/${id}`);

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">{doc.title}</h2>
        <p className="text-sm text-slate-500">
          {doc.product_name ?? "Sin producto"} ·{" "}
          {doc.country_iso ?? "GLOBAL"} · {doc.status} · {doc.chunk_count} chunks
        </p>
      </header>
      <article className="card whitespace-pre-wrap font-mono text-sm leading-relaxed text-slate-800">
        {doc.markdown ?? "Sin markdown disponible."}
      </article>
    </div>
  );
}
