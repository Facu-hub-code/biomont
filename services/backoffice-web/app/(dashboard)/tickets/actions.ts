"use server";

import { revalidatePath } from "next/cache";

import { apiRequest } from "@/lib/api";
import { formatApiError } from "@/lib/api-error";
import type { ActionFeedbackState } from "@/lib/form-action-state";

export async function updateTicketAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    const id = String(formData.get("id") ?? "");
    const newStatus = String(formData.get("status") ?? "");
    if (!id || !newStatus) return { ok: false, message: "Datos incompletos." };
    await apiRequest(`/tickets/${id}`, {
      method: "PATCH",
      json: { status: newStatus },
    });
    revalidatePath("/tickets");
    return { ok: true, message: "Ticket actualizado." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}
