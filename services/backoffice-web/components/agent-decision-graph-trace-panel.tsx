"use client";

import type { ReactNode } from "react";

import { ChunkContentModal } from "@/components/chunk-content-modal";

type TopScoreDisplay = {
  chunk_id?: string;
  chunk_label?: string;
  chunk_content?: string | null;
  chunk_found?: boolean;
  vec?: number;
  bm25?: number;
  final?: number;
};

export type GraphTraceStepDisplay = {
  node: string;
  outcome: string | null;
  latency_ms: number | null;
  display: Record<string, unknown>;
  payload_raw: Record<string, unknown> | null;
};

type Props = {
  steps: GraphTraceStepDisplay[];
};

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function renderDisplayValue(key: string, value: unknown): ReactNode {
  if (key === "top_scores" && Array.isArray(value)) {
    return (
      <ul className="mt-2 space-y-3">
        {(value as TopScoreDisplay[]).map((score, index) => (
          <li
            key={score.chunk_id ?? index}
            className="rounded border border-slate-200 bg-white p-3 text-sm"
          >
            <p className="font-medium text-slate-900">
              {score.chunk_label ?? "Chunk desconocido"}
            </p>
            <p className="mt-1 text-xs text-slate-600">
              vec={score.vec ?? "-"} · bm25={score.bm25 ?? "-"} · final={score.final ?? "-"}
            </p>
            <div className="mt-2">
              <ChunkContentModal
                title={score.chunk_label ?? "Chunk"}
                content={score.chunk_content ?? null}
                chunkFound={score.chunk_found ?? false}
                triggerLabel="Vista previa"
              />
            </div>
          </li>
        ))}
      </ul>
    );
  }

  if (key === "candidates" && Array.isArray(value)) {
    return (
      <ul className="mt-1 list-inside list-disc text-sm text-slate-700">
        {value.map((candidate, index) => {
          if (typeof candidate !== "object" || candidate === null) {
            return <li key={index}>{String(candidate)}</li>;
          }
          const row = candidate as Record<string, unknown>;
          const name = row.name ?? row.product_name ?? "Producto";
          const sim = row.similarity;
          return (
            <li key={index}>
              {String(name)}
              {sim !== undefined ? ` (${Number(sim).toFixed(3)})` : ""}
            </li>
          );
        })}
      </ul>
    );
  }

  if (typeof value === "object" && value !== null) {
    return (
      <pre className="mt-1 overflow-x-auto rounded bg-slate-100 p-2 text-xs">
        {formatJson(value)}
      </pre>
    );
  }

  return <span className="text-slate-800">{String(value)}</span>;
}

function renderStepBody(step: GraphTraceStepDisplay): ReactNode {
  const display = step.display;
  const entries = Object.entries(display);

  if (entries.length === 0) {
    return <p className="text-sm text-slate-500">Sin datos de display.</p>;
  }

  return (
    <dl className="mt-3 space-y-3 text-sm">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt className="font-medium capitalize text-slate-700">{key.replace(/_/g, " ")}</dt>
          <dd className="mt-1">{renderDisplayValue(key, value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function AgentDecisionGraphTracePanel({ steps }: Props) {
  if (steps.length === 0) {
    return <p className="text-sm text-slate-500">Sin pasos de grafo registrados.</p>;
  }

  return (
    <div className="space-y-3">
      {steps.map((step, index) => {
        const latency =
          step.latency_ms !== null && step.latency_ms !== undefined
            ? `${Math.round(step.latency_ms)}ms`
            : "-";
        const summary = `Paso ${index + 1}: ${step.node} · ${step.outcome ?? "n/a"} · ${latency}`;

        return (
          <details key={index} className="rounded-md border border-slate-200 p-3">
            <summary className="cursor-pointer text-sm font-medium text-slate-900">
              {summary}
            </summary>
            {renderStepBody(step)}
            {step.payload_raw && Object.keys(step.payload_raw).length > 0 ? (
              <details className="mt-4 rounded border border-slate-100 bg-slate-50 p-2">
                <summary className="cursor-pointer text-xs font-medium text-slate-600">
                  Ver payload técnico
                </summary>
                <pre className="mt-2 overflow-x-auto text-xs text-slate-700">
                  {formatJson(step.payload_raw)}
                </pre>
              </details>
            ) : null}
          </details>
        );
      })}
    </div>
  );
}
