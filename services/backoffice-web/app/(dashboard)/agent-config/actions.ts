"use server";

import { revalidatePath } from "next/cache";

import { apiRequest } from "@/lib/api";
import { formatApiError } from "@/lib/api-error";
import type { ActionFeedbackState } from "@/lib/form-action-state";

export async function saveAgentConfigAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    const top_k = Number(formData.get("top_k"));
    const candidate_k = Number(formData.get("candidate_k"));
    const full_corpus = formData.get("full_corpus_for_all_intents") === "on";
    const preamble = String(formData.get("classifier_preamble") ?? "").trim() || null;
    const intentsJson = String(formData.get("intents_json") ?? "[]");
    const intents = JSON.parse(intentsJson) as unknown[];
    if (!Array.isArray(intents) || intents.length === 0) {
      return { ok: false, message: "Debe haber al menos una intención configurada." };
    }
    await apiRequest("/agent-config/versions", {
      method: "POST",
      json: {
        top_k,
        candidate_k,
        full_corpus_for_all_intents: full_corpus,
        classifier_preamble: preamble,
        intents,
        activate: true,
      },
    });
    revalidatePath("/agent-config");
    return { ok: true, message: "Nueva versión de configuración guardada y activada." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}

export async function activateAgentConfigAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    const version = Number(formData.get("version"));
    if (!Number.isInteger(version)) {
      return { ok: false, message: "Versión inválida." };
    }
    await apiRequest(`/agent-config/versions/${version}/activate`, { method: "POST" });
    revalidatePath("/agent-config");
    return { ok: true, message: `Configuración v${version} activada.` };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}
