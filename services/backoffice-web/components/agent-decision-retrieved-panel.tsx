"use client";

import Link from "next/link";

import { ChunkContentModal } from "@/components/chunk-content-modal";

export type RetrievedItemEnriched = {
  document_id: string;
  chunk_id: string;
  similarity: number | null;
  document_title: string | null;
  chunk_label: string;
  chunk_content: string | null;
  chunk_found: boolean;
};

type Props = {
  items: RetrievedItemEnriched[];
};

function formatSimilarity(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(4);
}

export function AgentDecisionRetrievedPanel({ items }: Props) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-500">Sin chunks recuperados.</p>;
  }

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <article
          key={`${item.document_id}-${item.chunk_id}`}
          className="rounded-md border border-slate-200 bg-slate-50 p-4"
        >
          <h4 className="text-sm font-semibold text-slate-900">
            {item.document_title ?? "Documento desconocido"}
          </h4>
          <p className="mt-1 text-sm text-slate-700">{item.chunk_label}</p>
          <p className="mt-1 text-xs text-slate-500">
            Similitud: {formatSimilarity(item.similarity)}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-4">
            <Link
              href={`/documents/${item.document_id}`}
              className="text-sm font-medium text-teal-700 hover:text-teal-900 hover:underline"
            >
              Abrir documento
            </Link>
            <ChunkContentModal
              title={item.chunk_label}
              content={item.chunk_content}
              chunkFound={item.chunk_found}
            />
          </div>
        </article>
      ))}
    </div>
  );
}
