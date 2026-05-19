"use client";

import { useMemo, useState } from "react";

const DEFAULT_MAX_LINES = 24;

type Props = {
  text: string;
  maxLines?: number;
  className?: string;
  emptyLabel?: string;
};

export function ExpandableText({
  text,
  maxLines = DEFAULT_MAX_LINES,
  className = "",
  emptyLabel = "Sin contenido.",
}: Props) {
  const [expanded, setExpanded] = useState(false);

  const lines = useMemo(() => text.split("\n"), [text]);
  const isLong = lines.length > maxLines;
  const visibleText = expanded || !isLong ? text : lines.slice(0, maxLines).join("\n");

  if (!text.trim()) {
    return <p className="text-sm text-slate-500">{emptyLabel}</p>;
  }

  return (
    <div className="space-y-2">
      <article
        className={`whitespace-pre-wrap rounded-lg border border-slate-100 bg-slate-50/80 px-4 py-3 font-mono text-sm leading-relaxed text-slate-800 ${className}`}
      >
        {visibleText}
        {!expanded && isLong ? "\n…" : null}
      </article>
      {isLong ? (
        <button
          type="button"
          className="btn-secondary px-3 py-1.5 text-xs"
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Mostrar menos" : "Ver completo"}
        </button>
      ) : null}
    </div>
  );
}
