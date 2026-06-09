"use client";

import { useMemo, useState, useTransition } from "react";

import type { ActionFeedbackState } from "@/lib/form-action-state";

export type ComparisonColumnRow = {
  column_key: string;
  header_label: string;
  sort_order: number;
  display_tier: number;
  is_priority: boolean;
};

type Props = {
  productId: string;
  columns: ComparisonColumnRow[];
  saveAction: (
    prev: ActionFeedbackState | null,
    formData: FormData,
  ) => Promise<ActionFeedbackState>;
};

export function ComparisonColumnsForm({ productId, columns, saveAction }: Props) {
  const initial = useMemo(
    () => new Set(columns.filter((c) => c.is_priority).map((c) => c.column_key)),
    [columns],
  );
  const [selected, setSelected] = useState(initial);
  const [feedback, setFeedback] = useState<ActionFeedbackState>(null);
  const [pending, startTransition] = useTransition();

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formData = new FormData();
    formData.set("product_id", productId);
    for (const key of selected) {
      formData.append("priority_column_keys", key);
    }
    startTransition(async () => {
      const result = await saveAction(null, formData);
      setFeedback(result);
    });
  }

  if (!columns.length) {
    return null;
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-lg border border-slate-100 p-4">
      <div>
        <p className="text-sm font-medium text-slate-900">Columnas prioritarias del agente</p>
        <p className="text-xs text-slate-500">
          El resumen del comparador en WhatsApp muestra primero estas columnas. El resto queda
          disponible al pedir detalle o modo completo.
        </p>
      </div>
      <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {columns.map((col) => (
          <li key={col.column_key}>
            <label className="flex cursor-pointer items-start gap-2 rounded-md border border-slate-100 px-3 py-2 text-sm hover:bg-slate-50">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4"
                checked={selected.has(col.column_key)}
                onChange={() => toggle(col.column_key)}
              />
              <span>
                <span className="font-medium text-slate-800">{col.header_label}</span>
                <span className="block text-xs text-slate-400">{col.column_key}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
      <button
        type="submit"
        className="btn-primary disabled:cursor-wait"
        disabled={pending}
        aria-busy={pending}
      >
        {pending ? "Guardando…" : "Guardar prioridades"}
      </button>
      {feedback?.message ? (
        <p
          className={`text-sm ${feedback.ok ? "text-teal-700" : "text-red-600"}`}
          role="status"
        >
          {feedback.message}
        </p>
      ) : null}
    </form>
  );
}
