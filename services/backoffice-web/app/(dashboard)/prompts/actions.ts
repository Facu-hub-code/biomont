"use server";

import { revalidatePath } from "next/cache";

import { apiRequest } from "@/lib/api";
import { formatApiError } from "@/lib/api-error";
import type { ActionFeedbackState } from "@/lib/form-action-state";

export async function createPromptAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    const content = String(formData.get("content") ?? "").trim();
    if (!content) return { ok: false, message: "El contenido no puede estar vacío." };
    await apiRequest("/system-prompts", { method: "POST", json: { content } });
    revalidatePath("/prompts");
    return { ok: true, message: "Nueva versión del prompt guardada." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}

export async function activatePromptAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    const version = Number(formData.get("version"));
    if (!Number.isInteger(version)) {
      return { ok: false, message: "Versión inválida." };
    }
    await apiRequest(`/system-prompts/${version}/activate`, { method: "POST" });
    revalidatePath("/prompts");
    return { ok: true, message: `Prompt v${version} activado.` };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}
