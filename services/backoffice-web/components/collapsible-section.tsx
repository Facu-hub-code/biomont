"use client";

import { useState, type ReactNode } from "react";

type Props = {
  id: string;
  title: string;
  count?: number;
  defaultOpen?: boolean;
  children: ReactNode;
};

export function CollapsibleSection({
  id,
  title,
  count,
  defaultOpen = true,
  children,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const label = count != null ? `${title} (${count})` : title;

  return (
    <section id={id} className="card scroll-mt-28 space-y-3">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 text-left"
        aria-expanded={open}
        aria-controls={`${id}-content`}
      >
        <h3 className="text-sm font-semibold text-slate-800">{label}</h3>
        <span className="shrink-0 text-xs font-medium text-slate-500">
          {open ? "Ocultar" : "Mostrar"}
        </span>
      </button>
      {open ? (
        <div id={`${id}-content`} className="space-y-3">
          {children}
        </div>
      ) : null}
    </section>
  );
}
