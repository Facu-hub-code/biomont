"use client";

import { SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";

import { ActionFeedbackForm } from "@/components/action-feedback-form";
import { SubmitButton } from "@/components/submit-button";

import { activateAgentConfigAction, saveAgentConfigAction } from "./actions";

const KIND_OPTIONS = [
  { value: "ficha_tecnica", label: "Ficha" },
  { value: "bitacora", label: "Bitácora" },
  { value: "balotario", label: "Balotario" },
] as const;

export type IntentConfigRow = {
  intent_slug: string;
  display_label: string;
  classifier_hint: string;
  document_kinds: string[];
  sort_order: number;
  is_enabled: boolean;
};

export type AgentConfigVersion = {
  id: string;
  version: number;
  is_active: boolean;
  top_k: number;
  candidate_k: number;
  full_corpus_for_all_intents: boolean;
  classifier_preamble: string | null;
  created_at: string;
  intents: IntentConfigRow[];
};

type Props = {
  active: AgentConfigVersion | null;
  versions: AgentConfigVersion[];
  canMutate: boolean;
};

function cloneIntents(rows: IntentConfigRow[]): IntentConfigRow[] {
  return rows.map((r) => ({
    ...r,
    document_kinds: [...r.document_kinds],
  }));
}

export function AgentConfigEditor({ active, versions, canMutate }: Props) {
  const [topK, setTopK] = useState(active?.top_k ?? 6);
  const [candidateK, setCandidateK] = useState(active?.candidate_k ?? 25);
  const [fullCorpus, setFullCorpus] = useState(active?.full_corpus_for_all_intents ?? false);
  const [preamble, setPreamble] = useState(active?.classifier_preamble ?? "");
  const [intents, setIntents] = useState<IntentConfigRow[]>(() =>
    cloneIntents(active?.intents ?? []),
  );

  const intentsJson = useMemo(
    () =>
      JSON.stringify(
        intents.map((i) => ({
          intent_slug: i.intent_slug,
          display_label: i.display_label,
          classifier_hint: i.classifier_hint,
          document_kinds: i.document_kinds,
          sort_order: i.sort_order,
          is_enabled: i.is_enabled,
        })),
      ),
    [intents],
  );

  function updateIntent(index: number, patch: Partial<IntentConfigRow>) {
    setIntents((rows) =>
      rows.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    );
  }

  function toggleKind(index: number, kind: string) {
    setIntents((rows) =>
      rows.map((row, i) => {
        if (i !== index) return row;
        const kinds = row.document_kinds.includes(kind)
          ? row.document_kinds.filter((k) => k !== kind)
          : [...row.document_kinds, kind];
        return { ...row, document_kinds: kinds };
      }),
    );
  }

  return (
    <div className="space-y-10">
      <section className="card-static overflow-hidden border-teal-500/15 p-0">
        <div className="flex items-center gap-3 border-b border-teal-900/[0.06] bg-white/70 px-6 py-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-teal-600 text-white shadow-lg">
            <SlidersHorizontal className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-teal-700">
              Activa en runtime
            </p>
            <p className="text-lg font-semibold text-zinc-900">
              Versión v{active?.version ?? "—"}
            </p>
          </div>
        </div>
        <div className="space-y-2 px-6 py-4 text-sm text-zinc-600">
          <p>
            El agente recarga esta config en ~60s (caché). <strong>top_k</strong> = chunks
            que recibe el Answerer; <strong>kinds</strong> = filtro pre-retrieval por tipo de
            PDF cuando corpus completo está desactivado.
          </p>
        </div>
      </section>

      {canMutate && active ? (
        <ActionFeedbackForm
          action={saveAgentConfigAction}
          successMessage="Configuración guardada."
        >
          <div className="card-static space-y-8 border-white/90">
            <h3 className="text-sm font-semibold text-zinc-800">Guardar nueva versión</h3>
            <input type="hidden" name="intents_json" value={intentsJson} readOnly />
            <input type="hidden" name="top_k" value={topK} readOnly />
            <input type="hidden" name="candidate_k" value={candidateK} readOnly />
            {fullCorpus ? (
              <input type="hidden" name="full_corpus_for_all_intents" value="on" readOnly />
            ) : null}
            <input type="hidden" name="classifier_preamble" value={preamble} readOnly />

            <div className="grid gap-5 md:grid-cols-3">
              <div>
                <label className="form-label" htmlFor="top_k_input">
                  top_k (1–20)
                </label>
                <input
                  id="top_k_input"
                  type="number"
                  min={1}
                  max={20}
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  className="form-input"
                />
              </div>
              <div>
                <label className="form-label" htmlFor="candidate_k_input">
                  candidate_k (5–100)
                </label>
                <input
                  id="candidate_k_input"
                  type="number"
                  min={5}
                  max={100}
                  value={candidateK}
                  onChange={(e) => setCandidateK(Number(e.target.value))}
                  className="form-input"
                />
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-2 text-sm font-medium text-zinc-700">
                  <input
                    type="checkbox"
                    checked={fullCorpus}
                    onChange={(e) => setFullCorpus(e.target.checked)}
                    className="h-4 w-4 rounded border-zinc-300"
                  />
                  Corpus completo
                </label>
              </div>
            </div>
            <div>
              <label className="form-label" htmlFor="preamble_input">
                Preamble del clasificador
              </label>
              <textarea
                id="preamble_input"
                rows={3}
                value={preamble}
                onChange={(e) => setPreamble(e.target.value)}
                className="form-input text-sm"
              />
            </div>

            <div className="space-y-4">
              <h4 className="text-sm font-semibold text-zinc-800">Intenciones</h4>
              {intents.map((row, index) => (
                <div
                  key={row.intent_slug}
                  className="rounded-2xl border border-zinc-100 bg-zinc-50/50 p-4 space-y-3"
                >
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="font-mono text-xs font-semibold text-teal-800">
                      {row.intent_slug}
                    </span>
                    <label className="flex items-center gap-2 text-xs text-zinc-600">
                      <input
                        type="checkbox"
                        checked={row.is_enabled}
                        onChange={(e) =>
                          updateIntent(index, { is_enabled: e.target.checked })
                        }
                      />
                      Habilitado en prompt
                    </label>
                  </div>
                  <div>
                    <label className="form-label">Etiqueta (UI)</label>
                    <input
                      className="form-input text-sm"
                      value={row.display_label}
                      onChange={(e) =>
                        updateIntent(index, { display_label: e.target.value })
                      }
                    />
                  </div>
                  <div>
                    <label className="form-label">Hint para el clasificador</label>
                    <textarea
                      className="form-input text-sm"
                      rows={3}
                      value={row.classifier_hint}
                      onChange={(e) =>
                        updateIntent(index, { classifier_hint: e.target.value })
                      }
                    />
                  </div>
                  <div>
                    <span className="form-label">Tipos de documento (kinds)</span>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {KIND_OPTIONS.map((k) => (
                        <button
                          key={k.value}
                          type="button"
                          onClick={() => toggleKind(index, k.value)}
                          className={`filter-chip text-xs ${
                            row.document_kinds.includes(k.value)
                              ? "filter-chip-active"
                              : ""
                          }`}
                        >
                          {k.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <SubmitButton label="Guardar y activar versión" pendingLabel="Guardando…" />
          </div>
        </ActionFeedbackForm>
      ) : null}

      {versions.length > 0 ? (
        <section className="card-static space-y-3">
          <h3 className="text-sm font-semibold text-zinc-800">Historial de versiones</h3>
          <ul className="divide-y divide-zinc-100">
            {versions.map((v) => (
              <li key={v.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <span className="text-sm font-medium text-zinc-800">
                  v{v.version}
                  {v.is_active ? (
                    <span className="ml-2 badge-neutral text-[10px] uppercase">activa</span>
                  ) : null}
                </span>
                {canMutate && !v.is_active ? (
                  <ActionFeedbackForm action={activateAgentConfigAction}>
                    <input type="hidden" name="version" value={v.version} />
                    <SubmitButton label="Activar" pendingLabel="…" />
                  </ActionFeedbackForm>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
