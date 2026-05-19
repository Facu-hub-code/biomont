import { DocumentProductsPanel } from "@/components/document-products-panel";
import { apiRequest } from "@/lib/api";
import { requireRole } from "@/lib/auth";

type DocumentDetail = {
  id: string;
  title: string;
  product_name: string | null;
  country_iso: string | null;
  status: string;
  chunk_count: number;
  markdown: string | null;
};

type PaginatedResponse<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

type DocumentSection = {
  id: string;
  section_index: number;
  section_number: string | null;
  section_title: string | null;
  section_kind: string | null;
  page_start: number | null;
  page_end: number | null;
  raw_text: string | null;
};

type KnowledgeChunk = {
  id: string;
  chunk_index: number;
  kind: string;
  section_type: string | null;
  contains_table: boolean;
  contains_dose: boolean;
  token_count: number;
  content: string;
};

type LegacyChunk = {
  id: string;
  chunk_index: number;
  token_count: number;
  content: string;
};

type FaqEntry = {
  id: string;
  question: string;
  answer: string;
  source_page: number | null;
};

type LinkedProduct = {
  product_id: string;
  name: string;
  brand: string;
  is_primary: boolean;
};

type LinkedProductsResponse = {
  items: LinkedProduct[];
};

type CatalogProduct = {
  id: string;
  name: string;
  country_iso: string | null;
};

type ProductListResponse = {
  items: CatalogProduct[];
};

export default async function DocumentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const user = await requireRole(["admin", "scientist", "viewer"]);
  const canMutate = user.role === "admin" || user.role === "scientist";

  const [doc, sections, knowledgeChunks, legacyChunks, faqEntries, linkedProducts] =
    await Promise.all([
      apiRequest<DocumentDetail>(`/documents/${id}`),
      apiRequest<PaginatedResponse<DocumentSection>>(
        `/documents/${id}/sections?page=1&page_size=100`,
      ),
      apiRequest<PaginatedResponse<KnowledgeChunk>>(
        `/documents/${id}/knowledge-chunks?page=1&page_size=100`,
      ),
      apiRequest<PaginatedResponse<LegacyChunk>>(
        `/documents/${id}/document-chunks?page=1&page_size=100`,
      ),
      apiRequest<PaginatedResponse<FaqEntry>>(
        `/documents/${id}/faq-entries?page=1&page_size=100`,
      ),
      apiRequest<LinkedProductsResponse>(`/documents/${id}/products`),
    ]);

  let catalog: CatalogProduct[] = [];
  try {
    const productList = await apiRequest<ProductListResponse>(
      "/products?page=1&page_size=200",
    );
    catalog = productList.items;
  } catch {
    catalog = [];
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">{doc.title}</h2>
        <p className="text-sm text-slate-500">
          {doc.product_name ?? "Sin producto"} ·{" "}
          {doc.country_iso ?? "GLOBAL"} · {doc.status} · {doc.chunk_count} chunks
        </p>
      </header>

      <DocumentProductsPanel
        documentId={id}
        catalog={catalog}
        linked={linkedProducts.items}
        canMutate={canMutate}
      />

      <div role="tablist" className="flex flex-wrap gap-2">
        <a href="#tab-markdown" className="btn-secondary text-xs">
          Markdown
        </a>
        <a href="#tab-secciones" className="btn-secondary text-xs">
          Secciones
        </a>
        <a href="#tab-chunks" className="btn-secondary text-xs">
          Chunks (retrieval)
        </a>
        <a href="#tab-faq" className="btn-secondary text-xs">
          FAQ
        </a>
        <a href="#tab-legacy" className="btn-secondary text-xs">
          Legacy chunks
        </a>
      </div>

      <section id="tab-markdown" className="card space-y-2">
        <h3 className="text-sm font-semibold text-slate-700">Texto / Markdown</h3>
        <article className="whitespace-pre-wrap font-mono text-sm leading-relaxed text-slate-800">
          {doc.markdown ?? "Sin markdown disponible."}
        </article>
      </section>

      <section id="tab-secciones" className="card space-y-2">
        <h3 className="text-sm font-semibold text-slate-700">Secciones ({sections.total})</h3>
        {sections.items.length === 0 ? (
          <p className="text-sm text-slate-500">No hay secciones cargadas.</p>
        ) : (
          <div className="space-y-2">
            {sections.items.map((section) => (
              <details key={section.id} className="rounded-md border border-slate-200 p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  #{section.section_index} {section.section_number ?? ""} {section.section_title ?? "Sin titulo"}
                </summary>
                <p className="mt-2 text-xs text-slate-500">
                  kind: {section.section_kind ?? "-"} · paginas: {section.page_start ?? "-"} -{" "}
                  {section.page_end ?? "-"}
                </p>
                <div className="mt-2 space-y-1">
                  <p className="text-xs text-slate-400">Texto completo guardado en BD</p>
                  <div className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded border border-slate-100 bg-slate-50/80 px-3 py-2 text-sm text-slate-700">
                    {section.raw_text ?? "Sin texto."}
                  </div>
                </div>
              </details>
            ))}
          </div>
        )}
      </section>

      <section id="tab-chunks" className="card space-y-2">
        <h3 className="text-sm font-semibold text-slate-700">
          Chunks (retrieval) ({knowledgeChunks.total})
        </h3>
        {knowledgeChunks.items.length === 0 ? (
          <p className="text-sm text-slate-500">
            Este documento no tiene knowledge chunks; puede requerir reingesta.
          </p>
        ) : (
          <table className="table-default">
            <thead>
              <tr>
                <th>#</th>
                <th>Kind</th>
                <th>Section</th>
                <th>Banderas</th>
                <th>Tokens</th>
                <th>Contenido</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {knowledgeChunks.items.map((chunk) => (
                <tr key={chunk.id}>
                  <td>{chunk.chunk_index}</td>
                  <td>{chunk.kind}</td>
                  <td>{chunk.section_type ?? "-"}</td>
                  <td>
                    {chunk.contains_table ? "tabla " : ""}
                    {chunk.contains_dose ? "dosis" : "-"}
                  </td>
                  <td>{chunk.token_count}</td>
                  <td className="max-w-xl">
                    <div className="max-h-48 overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed text-slate-800">
                      {chunk.content}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section id="tab-faq" className="card space-y-2">
        <h3 className="text-sm font-semibold text-slate-700">FAQ ({faqEntries.total})</h3>
        {faqEntries.items.length === 0 ? (
          <p className="text-sm text-slate-500">Sin entradas FAQ para este documento.</p>
        ) : (
          <div className="space-y-3">
            {faqEntries.items.map((entry) => (
              <article key={entry.id} className="rounded-md border border-slate-200 p-3">
                <p className="text-sm font-medium text-slate-900">{entry.question}</p>
                <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{entry.answer}</p>
                <p className="mt-1 text-xs text-slate-500">Pagina fuente: {entry.source_page ?? "-"}</p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section id="tab-legacy" className="card space-y-2">
        <h3 className="text-sm font-semibold text-slate-700">Legacy chunks ({legacyChunks.total})</h3>
        {legacyChunks.items.length === 0 ? (
          <p className="text-sm text-slate-500">Sin document_chunks legacy.</p>
        ) : (
          <table className="table-default">
            <thead>
              <tr>
                <th>#</th>
                <th>Tokens</th>
                <th>Contenido</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {legacyChunks.items.map((chunk) => (
                <tr key={chunk.id}>
                  <td>{chunk.chunk_index}</td>
                  <td>{chunk.token_count}</td>
                  <td className="max-w-xl">
                    <div className="max-h-48 overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed text-slate-800">
                      {chunk.content}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
