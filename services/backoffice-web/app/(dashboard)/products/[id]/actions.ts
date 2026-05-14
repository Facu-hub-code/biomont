"use server";

import { revalidatePath } from "next/cache";

import { apiRequest } from "@/lib/api";
import { formatApiError } from "@/lib/api-error";
import type { ActionFeedbackState } from "@/lib/form-action-state";
import { requireRole } from "@/lib/auth";

export async function updateProductAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin", "scientist"]);
    const id = String(formData.get("id") ?? "");
    if (!id) return { ok: false, message: "Falta el identificador del producto." };
    const payload = {
      name: String(formData.get("name") ?? "").trim() || undefined,
      brand: String(formData.get("brand") ?? "").trim() || undefined,
      duration_type: String(formData.get("duration_type") ?? "").trim() || null,
      description: String(formData.get("description") ?? "").trim() || null,
      country_iso: String(formData.get("country_iso") ?? "").trim().toUpperCase() || null,
    };
    await apiRequest(`/products/${id}`, { method: "PATCH", json: payload });
    revalidatePath(`/products/${id}`);
    revalidatePath("/products");
    return { ok: true, message: "Cambios guardados." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}

export async function deleteProductAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin"]);
    const id = String(formData.get("id") ?? "");
    if (!id) return { ok: false, message: "Falta el identificador del producto." };
    await apiRequest(`/products/${id}`, { method: "DELETE" });
    revalidatePath("/products");
    return { ok: true, message: "Producto eliminado." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}

export async function createAliasAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin", "scientist"]);
    const productId = String(formData.get("product_id") ?? "");
    const alias = String(formData.get("alias") ?? "").trim();
    if (!productId || !alias) return { ok: false, message: "Alias y producto son obligatorios." };
    await apiRequest(`/products/${productId}/aliases`, {
      method: "POST",
      json: {
        alias,
        source: String(formData.get("source") ?? "manual"),
        confidence: Number(formData.get("confidence") ?? 1),
      },
    });
    revalidatePath(`/products/${productId}`);
    return { ok: true, message: "Alias agregado." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}

export async function updateAliasAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin", "scientist"]);
    const productId = String(formData.get("product_id") ?? "");
    const aliasId = String(formData.get("alias_id") ?? "");
    const alias = String(formData.get("alias") ?? "").trim();
    if (!productId || !aliasId || !alias) {
      return { ok: false, message: "Datos de alias incompletos." };
    }
    await apiRequest(`/products/${productId}/aliases/${aliasId}`, {
      method: "PATCH",
      json: {
        alias,
        source: String(formData.get("source") ?? "manual"),
        confidence: Number(formData.get("confidence") ?? 1),
      },
    });
    revalidatePath(`/products/${productId}`);
    return { ok: true, message: "Alias actualizado." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}

export async function deleteAliasAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin", "scientist"]);
    const productId = String(formData.get("product_id") ?? "");
    const aliasId = String(formData.get("alias_id") ?? "");
    if (!productId || !aliasId) return { ok: false, message: "Falta identificador del alias." };
    await apiRequest(`/products/${productId}/aliases/${aliasId}`, { method: "DELETE" });
    revalidatePath(`/products/${productId}`);
    return { ok: true, message: "Alias eliminado." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}
