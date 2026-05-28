"use client";

import { useEffect, useState } from "react";

type Props = {
  title: string;
  content: string | null;
  chunkFound?: boolean;
  triggerLabel?: string;
  triggerClassName?: string;
};

export function ChunkContentModal({
  title,
  content,
  chunkFound = true,
  triggerLabel = "Ver contenido del chunk",
  triggerClassName = "text-sm font-medium text-teal-700 hover:text-teal-900 hover:underline",
}: Props) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  return (
    <>
      <button type="button" className={triggerClassName} onClick={() => setOpen(true)}>
        {triggerLabel}
      </button>
      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
          role="presentation"
          onClick={() => setOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="chunk-content-modal-title"
            className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-lg border border-slate-200 bg-white shadow-lg"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
              <h3
                id="chunk-content-modal-title"
                className="text-lg font-semibold text-slate-900"
              >
                {title}
              </h3>
              <button
                type="button"
                className="btn-secondary shrink-0"
                onClick={() => setOpen(false)}
              >
                Cerrar
              </button>
            </div>
            <div className="overflow-y-auto px-5 py-4">
              {!chunkFound || !content ? (
                <p className="text-sm text-slate-600">
                  El contenido de este chunk no está disponible (puede haber sido eliminado o
                  reingestado).
                </p>
              ) : (
                <pre className="whitespace-pre-wrap font-sans text-sm text-slate-800">
                  {content}
                </pre>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
