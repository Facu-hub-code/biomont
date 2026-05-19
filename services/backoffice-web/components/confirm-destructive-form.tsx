"use client";

import { useState, type ReactNode } from "react";

import { ActionFeedbackForm } from "@/components/action-feedback-form";
import { SubmitButton } from "@/components/submit-button";
import type { ActionFeedbackState } from "@/lib/form-action-state";

type Props = {
  action: (
    prevState: ActionFeedbackState | null,
    formData: FormData,
  ) => Promise<ActionFeedbackState>;
  triggerLabel: string;
  dialogTitle: string;
  dialogDescription: string;
  confirmLabel?: string;
  successMessage?: string;
  redirectOnSuccess?: string;
  children: ReactNode;
};

export function ConfirmDestructiveForm({
  action,
  triggerLabel,
  dialogTitle,
  dialogDescription,
  confirmLabel = "Eliminar",
  successMessage,
  redirectOnSuccess,
  children,
}: Props) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        className="rounded px-3 py-1.5 text-sm font-medium text-red-700 ring-1 ring-red-200 hover:bg-red-50"
        onClick={() => setOpen(true)}
      >
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
            aria-labelledby="confirm-destructive-title"
            className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-6 shadow-lg"
            onClick={(event) => event.stopPropagation()}
          >
            <h3 id="confirm-destructive-title" className="text-lg font-semibold text-slate-900">
              {dialogTitle}
            </h3>
            <p className="mt-2 text-sm text-slate-600">{dialogDescription}</p>
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setOpen(false)}
              >
                Cancelar
              </button>
              <ActionFeedbackForm
                action={action}
                successMessage={successMessage}
                redirectOnSuccess={redirectOnSuccess}
              >
                {children}
                <SubmitButton
                  label={confirmLabel}
                  pendingLabel="Eliminando…"
                  variant="dangerLink"
                  className="text-sm no-underline"
                />
              </ActionFeedbackForm>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
