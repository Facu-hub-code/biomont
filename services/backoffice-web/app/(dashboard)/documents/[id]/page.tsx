import { DocumentDetailView } from "@/components/document-detail-view";
import type { LinkedProduct } from "@/components/document-products-panel";
import { apiRequest } from "@/lib/api";
import { requireRole } from "@/lib/auth";

type DocumentDetail = {
  id: string;
  title: string;
  product_name: string | null;
  linked_products?: LinkedProduct[];
  country_iso: string | null;
  status: string;
  chunk_count: number;
  markdown: string | null;
};

function formatProductLine(doc: DocumentDetail): string {
  if (doc.linked_products?.length) {
    return doc.linked_products
      .map((p) => (p.is_primary ? `${p.name} (primario)` : p.name))
      .join(", ");
  }
  return doc.product_name ?? "Sin producto";
}

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

type LinkedProductsResponse = {
  items: LinkedProduct[];
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

  const metaLine = `${formatProductLine(doc)} · ${doc.country_iso ?? "GLOBAL"} · ${doc.status} · ${doc.chunk_count} chunks`;

  return (
    <DocumentDetailView
      documentId={doc.id}
      title={doc.title}
      metaLine={metaLine}
      chunkCount={doc.chunk_count}
      canMutate={canMutate}
      markdown={doc.markdown}
      sections={sections.items}
      sectionsTotal={sections.total}
      knowledgeChunks={knowledgeChunks.items}
      knowledgeChunksTotal={knowledgeChunks.total}
      legacyChunks={legacyChunks.items}
      legacyChunksTotal={legacyChunks.total}
      faqEntries={faqEntries.items}
      faqEntriesTotal={faqEntries.total}
      linkedProducts={linkedProducts.items}
    />
  );
}
