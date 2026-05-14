"use server";

import { revalidatePath } from "next/cache";

import { apiRequest } from "@/lib/api";
import { formatApiError } from "@/lib/api-error";
import type { ActionFeedbackState } from "@/lib/form-action-state";

export async function createRtcAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    const payload = {
      phone_e164: String(formData.get("phone_e164") ?? "").trim(),
      name: String(formData.get("name") ?? "").trim(),
      enabled: formData.get("enabled") === "on",
      country_isos: String(formData.get("country_isos") ?? "")
        .split(",")
        .map((c) => c.trim().toUpperCase())
        .filter(Boolean),
    };
    if (!payload.phone_e164 || !payload.name) {
      return { ok: false, message: "Teléfono y nombre son obligatorios." };
    }
    await apiRequest("/rtcs", { method: "POST", json: payload });
    revalidatePath("/rtcs");
    return { ok: true, message: "RTC creado." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}

export async function deleteRtcAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    const id = String(formData.get("id") ?? "");
    if (!id) return { ok: false, message: "Falta identificador." };
    await apiRequest(`/rtcs/${id}`, { method: "DELETE" });
    revalidatePath("/rtcs");
    return { ok: true, message: "RTC eliminado." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}
