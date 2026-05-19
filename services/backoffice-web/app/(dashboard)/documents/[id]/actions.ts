"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { apiRequest } from "@/lib/api";
import { formatApiError } from "@/lib/api-error";
import type { ActionFeedbackState } from "@/lib/form-action-state";
import { requireRole } from "@/lib/auth";

export async function saveDocumentProductsAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin", "scientist"]);
    const documentId = String(formData.get("document_id") ?? "");
    if (!documentId) {
      return { ok: false, message: "Falta el identificador del documento." };
    }

    const selected = formData.getAll("product_ids").map(String).filter(Boolean);
    const primary = String(formData.get("primary_product_id") ?? "").trim() || null;

    await apiRequest(`/documents/${documentId}/products`, {
      method: "PATCH",
      json: {
        product_ids: selected,
        primary_product_id: primary,
      },
    });

    revalidatePath(`/documents/${documentId}`);
    revalidatePath("/products");
    return { ok: true, message: "Productos vinculados actualizados." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}

export async function deleteDocumentAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  await requireRole(["admin", "scientist"]);
  const id = String(formData.get("id") ?? "");
  if (!id) return { ok: false, message: "Falta el identificador del documento." };

  try {
    await apiRequest(`/documents/${id}`, { method: "DELETE" });
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }

  revalidatePath("/documents");
  revalidatePath(`/documents/${id}`);
  redirect("/documents?deleted=1");
}
