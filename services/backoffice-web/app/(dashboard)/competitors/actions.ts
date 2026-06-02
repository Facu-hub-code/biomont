"use server";

import { revalidatePath } from "next/cache";

import { apiRequest } from "@/lib/api";
import { formatApiError } from "@/lib/api-error";
import type { ActionFeedbackState } from "@/lib/form-action-state";
import { requireRole } from "@/lib/auth";

export async function createCompetitorAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin", "scientist"]);
    const name = String(formData.get("name") ?? "").trim();
    if (!name) return { ok: false, message: "Nombre obligatorio." };
    await apiRequest("/competitors", {
      method: "POST",
      json: {
        name,
        brand: String(formData.get("brand") ?? "").trim() || null,
        is_internal: formData.get("is_internal") === "on",
      },
    });
    revalidatePath("/competitors");
    return { ok: true, message: "Competidor creado." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}
