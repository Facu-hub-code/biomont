"use client";

import { useActionState, useEffect, type FormEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import type { ActionFeedbackState } from "@/lib/form-action-state";
import { useToast } from "@/components/toast-provider";

type Props = {
  action: (
    prevState: ActionFeedbackState | null,
    formData: FormData,
  ) => Promise<ActionFeedbackState>;
  children: ReactNode;
  successMessage?: string;
  /** Tras éxito, navegar (p. ej. borrar producto → /products). El toast sigue visible (provider en layout). */
  redirectOnSuccess?: string;
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void;
};

export function ActionFeedbackForm({
  action,
  children,
  successMessage,
  redirectOnSuccess,
  onSubmit,
}: Props) {
  const router = useRouter();
  const { showToast } = useToast();
  const [state, formAction] = useActionState(action, null);

  useEffect(() => {
    if (state == null) return;
    const dedupeKey = JSON.stringify(state);

    if (state.ok) {
      showToast("success", state.message ?? successMessage ?? "Operación completada.", dedupeKey);
      if (redirectOnSuccess) {
        router.replace(redirectOnSuccess);
      } else {
        router.refresh();
      }
    } else {
      showToast("error", state.message, dedupeKey);
    }
  }, [state, successMessage, redirectOnSuccess, router, showToast]);

  return (
    <form action={formAction} onSubmit={onSubmit}>
      {children}
    </form>
  );
}
