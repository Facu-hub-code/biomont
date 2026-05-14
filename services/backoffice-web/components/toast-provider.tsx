"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";

type ToastKind = "success" | "error";

export type ToastItem = {
  id: string;
  kind: ToastKind;
  message: string;
};

type ToastContextValue = {
  showToast: (kind: ToastKind, message: string, dedupeKey?: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast debe usarse dentro de ToastProvider");
  }
  return ctx;
}

const DEDUPE_MS = 900;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const recent = useRef<Map<string, number>>(new Map());

  const remove = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback((kind: ToastKind, message: string, dedupeKey?: string) => {
    const key = dedupeKey ?? `${kind}:${message}`;
    const now = Date.now();
    const last = recent.current.get(key);
    if (last !== undefined && now - last < DEDUPE_MS) return;
    recent.current.set(key, now);

    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${now}-${Math.random().toString(36).slice(2)}`;

    const item: ToastItem = { id, kind, message: message.trim() || " " };
    setToasts((prev) => [...prev, item]);

    const ttl = kind === "error" ? 10_000 : 6_000;
    window.setTimeout(() => remove(id), ttl);
  }, [remove]);

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed right-4 top-4 z-[100] flex max-w-md flex-col gap-2"
        aria-live="polite"
      >
        {toasts.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`pointer-events-auto rounded-md border px-4 py-3 text-left text-sm shadow-lg transition-colors ${
              t.kind === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                : "border-red-200 bg-red-50 text-red-900"
            }`}
            onClick={() => remove(t.id)}
          >
            <span className="font-medium">
              {t.kind === "success" ? "Listo" : "Error"}
            </span>
            <p className="mt-1 whitespace-pre-wrap break-words text-xs opacity-90">{t.message}</p>
            <span className="mt-2 block text-[10px] uppercase tracking-wide opacity-70">
              Clic para cerrar
            </span>
          </button>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
