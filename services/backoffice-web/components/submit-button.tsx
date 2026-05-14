"use client";

import { useFormStatus } from "react-dom";

type Props = {
  label: string;
  pendingLabel?: string;
  className?: string;
  variant?: "primary" | "secondary" | "dangerLink";
};

export function SubmitButton({
  label,
  pendingLabel = "Guardando…",
  className,
  variant = "primary",
}: Props) {
  const { pending } = useFormStatus();
  const base =
    variant === "primary"
      ? "btn-primary"
      : variant === "secondary"
        ? "btn-secondary"
        : "rounded px-2 py-1 text-sm text-red-600 underline-offset-2 hover:underline disabled:opacity-50";
  const combined = `${base}${className ? ` ${className}` : ""} disabled:cursor-wait`;

  return (
    <button
      type="submit"
      className={combined}
      disabled={pending}
      aria-busy={pending}
    >
      {pending ? (
        <span className="inline-flex items-center justify-center gap-2">
          <Spinner light={variant === "primary"} />
          {pendingLabel}
        </span>
      ) : (
        label
      )}
    </button>
  );
}

function Spinner({ light }: { light?: boolean }) {
  return (
    <span
      className={`h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-t-transparent ${
        light ? "border-white" : "border-slate-500"
      }`}
      aria-hidden
    />
  );
}
