"use client";

import {
  DocumentProductsPanel,
  type LinkedProduct,
} from "@/components/document-products-panel";
import { ConfirmDestructiveForm } from "@/components/confirm-destructive-form";
import { deleteDocumentAction } from "@/app/(dashboard)/documents/[id]/actions";
import { CollapsibleSection } from "@/components/collapsible-section";
import { DocumentSectionNav } from "@/components/document-section-nav";
import { ExpandableText } from "@/components/expandable-text";
const LOW_TOKEN_THRESHOLD = 50;

const SECTION_LINKS = [
  { id: "tab-productos", label: "Productos" },
  { id: "tab-markdown", label: "Markdown" },
  { id: "tab-secciones", label: "Secciones" },
  { id: "tab-chunks", label: "Chunks (retrieval)" },
  { id: "tab-faq", label: "FAQ" },
  { id: "tab-legacy", label: "Legacy chunks" },
];

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

type Props = {
  documentId: string;
  title: string;
  metaLine: string;
  chunkCount: number;
  canMutate: boolean;
  markdown: string | null;
  sections: DocumentSection[];
  sectionsTotal: number;
  knowledgeChunks: KnowledgeChunk[];
  knowledgeChunksTotal: number;
  legacyChunks: LegacyChunk[];
  legacyChunksTotal: number;
  faqEntries: FaqEntry[];
  faqEntriesTotal: number;
  linkedProducts: LinkedProduct[];
};

function countLowTokenChunks(chunks: { token_count: number }[]) {
  return chunks.filter((chunk) => chunk.token_count < LOW_TOKEN_THRESHOLD).length;
}

function LowTokenSectionWarning({ count }: { count: number }) {
  if (count === 0) {
    return null;
  }

  const label = count === 1 ? "chunk" : "chunks";
  return (
    <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
      {count} {label} con menos de 50 tokens — pueden tener baja calidad en retrieval
    </p>
  );
}

function TokenCountCell({ count }: { count: number }) {
  const isLow = count < LOW_TOKEN_THRESHOLD;

  if (!isLow) {
    return <td>{count}</td>;
  }

  return (
    <td>
      <span className="inline-flex items-center gap-1.5">
        {count}
        <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800">
          &lt;50
        </span>
      </span>
    </td>
  );
}

export function DocumentDetailView({
  documentId,
  title,
  metaLine,
  chunkCount,
  canMutate,
  markdown,
  sections,
  sectionsTotal,
  knowledgeChunks,
  knowledgeChunksTotal,
  legacyChunks,
  legacyChunksTotal,
  faqEntries,
  faqEntriesTotal,
  linkedProducts,
}: Props) {
  const lowKnowledgeTokenCount = countLowTokenChunks(knowledgeChunks);
  const lowLegacyTokenCount = countLowTokenChunks(legacyChunks);

  return (
    <div className="space-y-6">
      <header className="page-header flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="page-title">{title}</h2>
          <p className="page-subtitle">{metaLine}</p>
        </div>
        {canMutate ? (
          <ConfirmDestructiveForm
            action={deleteDocumentAction}
            triggerLabel="Eliminar documento"
            dialogTitle="¿Eliminar este documento?"
            dialogDescription={`Esta acción es irreversible. Se borrarán el documento "${title}", sus ${chunkCount} chunks de retrieval, secciones, entradas FAQ y vínculos con productos.`}
            successMessage="Documento eliminado."
          >
            <input type="hidden" name="id" value={documentId} />
          </ConfirmDestructiveForm>
        ) : null}
      </header>

      <DocumentSectionNav sections={SECTION_LINKS} />

      <CollapsibleSection id="tab-productos" title="Productos del catálogo" defaultOpen>
        <DocumentProductsPanel linked={linkedProducts} />
      </CollapsibleSection>

      <CollapsibleSection id="tab-markdown" title="Texto / Markdown" defaultOpen={false}>
        <ExpandableText
          text={markdown ?? ""}
          emptyLabel="Sin markdown disponible."
          maxLines={20}
        />
      </CollapsibleSection>

      <CollapsibleSection id="tab-secciones" title="Secciones" count={sectionsTotal}>
        {sections.length === 0 ? (
          <p className="text-sm text-slate-500">No hay secciones cargadas.</p>
        ) : (
          <div className="space-y-2">
            {sections.map((section) => (
              <details
                key={section.id}
                className="rounded-lg border border-slate-200 bg-slate-50/40 p-3"
              >
                <summary className="cursor-pointer text-sm font-medium text-slate-800">
                  #{section.section_index} {section.section_number ?? ""}{" "}
                  {section.section_title ?? "Sin titulo"}
                </summary>
                <p className="mt-2 text-xs text-slate-500">
                  kind: {section.section_kind ?? "-"} · paginas: {section.page_start ?? "-"} -{" "}
                  {section.page_end ?? "-"}
                </p>
                <div className="mt-3">
                  <ExpandableText text={section.raw_text ?? ""} maxLines={12} emptyLabel="Sin texto." />
                </div>
              </details>
            ))}
          </div>
        )}
      </CollapsibleSection>

      <CollapsibleSection
        id="tab-chunks"
        title="Chunks (retrieval)"
        count={knowledgeChunksTotal}
        defaultOpen={false}
      >
        {knowledgeChunks.length === 0 ? (
          <p className="text-sm text-slate-500">
            Este documento no tiene knowledge chunks; puede requerir reingesta.
          </p>
        ) : (
          <div className="space-y-3">
            <LowTokenSectionWarning count={lowKnowledgeTokenCount} />
            <div className="table-shell overflow-x-auto">
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
                {knowledgeChunks.map((chunk) => (
                  <tr key={chunk.id}>
                    <td>{chunk.chunk_index}</td>
                    <td>{chunk.kind}</td>
                    <td>{chunk.section_type ?? "-"}</td>
                    <td>
                      {chunk.contains_table ? "tabla " : ""}
                      {chunk.contains_dose ? "dosis" : "-"}
                    </td>
                    <TokenCountCell count={chunk.token_count} />
                    <td className="max-w-xl">
                      <ExpandableText text={chunk.content} maxLines={8} className="font-sans text-xs" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        )}
      </CollapsibleSection>

      <CollapsibleSection id="tab-faq" title="FAQ" count={faqEntriesTotal} defaultOpen={false}>
        {faqEntries.length === 0 ? (
          <p className="text-sm text-slate-500">Sin entradas FAQ para este documento.</p>
        ) : (
          <div className="space-y-3">
            {faqEntries.map((entry) => (
              <article
                key={entry.id}
                className="rounded-lg border border-slate-200 bg-slate-50/40 p-4"
              >
                <p className="text-sm font-medium text-slate-900">{entry.question}</p>
                <ExpandableText
                  text={entry.answer}
                  maxLines={6}
                  className="mt-2 font-sans"
                />
                <p className="mt-2 text-xs text-slate-500">
                  Pagina fuente: {entry.source_page ?? "-"}
                </p>
              </article>
            ))}
          </div>
        )}
      </CollapsibleSection>

      <CollapsibleSection
        id="tab-legacy"
        title="Legacy chunks"
        count={legacyChunksTotal}
        defaultOpen={false}
      >
        {legacyChunks.length === 0 ? (
          <p className="text-sm text-slate-500">Sin document_chunks legacy.</p>
        ) : (
          <div className="space-y-3">
            <LowTokenSectionWarning count={lowLegacyTokenCount} />
            <div className="table-shell overflow-x-auto">
              <table className="table-default">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Tokens</th>
                    <th>Contenido</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {legacyChunks.map((chunk) => (
                    <tr key={chunk.id}>
                      <td>{chunk.chunk_index}</td>
                      <TokenCountCell count={chunk.token_count} />
                      <td className="max-w-xl">
                        <ExpandableText
                          text={chunk.content}
                          maxLines={8}
                          className="font-sans text-xs"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </CollapsibleSection>
    </div>
  );
}
