"use server";

import { revalidatePath } from "next/cache";

import { apiRequest } from "@/lib/api";
import { formatApiError } from "@/lib/api-error";
import type { ActionFeedbackState } from "@/lib/form-action-state";
import { requireRole } from "@/lib/auth";

export async function createProductAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin", "scientist"]);
    const payload = {
      name: String(formData.get("name") ?? "").trim(),
      brand: String(formData.get("brand") ?? "Biomont").trim() || "Biomont",
      duration_type: String(formData.get("duration_type") ?? "").trim() || null,
      description: String(formData.get("description") ?? "").trim() || null,
      country_iso: String(formData.get("country_iso") ?? "").trim().toUpperCase() || null,
    };
    if (!payload.name) {
      return { ok: false, message: "El nombre es obligatorio." };
    }
    await apiRequest("/products", { method: "POST", json: payload });
    revalidatePath("/products");
    return { ok: true, message: "Producto creado correctamente." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}
