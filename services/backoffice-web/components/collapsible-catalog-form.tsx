"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";

type Props = {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
};

export function CollapsibleCatalogForm({ title, children, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-2 rounded-2xl border border-teal-600/20 bg-white/90 px-4 py-2.5 text-sm font-semibold text-teal-800 shadow-sm ring-1 ring-teal-900/[0.06] transition hover:border-teal-400/40 hover:bg-teal-50/50"
        aria-expanded={open}
      >
        {open ? <X className="h-4 w-4" aria-hidden /> : <Plus className="h-4 w-4" aria-hidden />}
        {open ? "Cancelar" : title}
      </button>
      {open ? children : null}
    </div>
  );
}
