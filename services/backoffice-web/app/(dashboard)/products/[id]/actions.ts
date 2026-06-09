"use server";

import { revalidatePath } from "next/cache";

import { apiRequest, getAccessToken, getApiBaseUrl } from "@/lib/api";
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

export async function linkDocumentAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin", "scientist"]);
    const productId = String(formData.get("product_id") ?? "");
    const documentId = String(formData.get("document_id") ?? "").trim();
    if (!productId || !documentId) {
      return { ok: false, message: "Producto y documento son obligatorios." };
    }
    const isPrimary = formData.get("is_primary") === "on";
    await apiRequest(`/products/${productId}/documents`, {
      method: "POST",
      json: { document_id: documentId, is_primary: isPrimary },
    });
    revalidatePath(`/products/${productId}`);
    revalidatePath(`/documents/${documentId}`);
    return { ok: true, message: "Documento vinculado." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}

export async function unlinkDocumentAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin", "scientist"]);
    const productId = String(formData.get("product_id") ?? "");
    const documentId = String(formData.get("document_id") ?? "");
    if (!productId || !documentId) {
      return { ok: false, message: "Faltan identificadores." };
    }
    await apiRequest(`/products/${productId}/documents/${documentId}`, {
      method: "DELETE",
    });
    revalidatePath(`/products/${productId}`);
    revalidatePath(`/documents/${documentId}`);
    return { ok: true, message: "Vinculo eliminado." };
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

export async function upsertDosingProfileAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin", "scientist"]);
    const productId = String(formData.get("product_id") ?? "");
    const species = String(formData.get("species") ?? "").trim();
    if (!productId || !species) {
      return { ok: false, message: "Producto y especie son obligatorios." };
    }
    await apiRequest(`/products/${productId}/dosing/profile`, {
      method: "PUT",
      json: {
        species,
        supports_dose_calculation: formData.get("supports_dose_calculation") === "on",
        min_weight_kg: String(formData.get("min_weight_kg") ?? "").trim() || null,
        max_weight_kg: String(formData.get("max_weight_kg") ?? "").trim() || null,
      },
    });
    revalidatePath(`/products/${productId}`);
    return { ok: true, message: "Perfil de dosis guardado." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}

export async function createDosingRuleAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin", "scientist"]);
    const productId = String(formData.get("product_id") ?? "");
    const profileId = String(formData.get("profile_id") ?? "");
    const ruleType = String(formData.get("rule_type") ?? "weight_band");
    if (!productId || !profileId) {
      return { ok: false, message: "Faltan identificadores." };
    }
    await apiRequest(`/products/${productId}/dosing/profiles/${profileId}/rules`, {
      method: "POST",
      json: {
        rule_type: ruleType,
        label: String(formData.get("label") ?? "").trim() || null,
        formula_numerator: String(formData.get("formula_numerator") ?? "").trim() || null,
        formula_denominator: String(formData.get("formula_denominator") ?? "1").trim() || "1",
        formula_per_kg: formData.get("formula_per_kg") === "on",
        weight_min_kg: String(formData.get("weight_min_kg") ?? "").trim() || null,
        weight_max_kg: String(formData.get("weight_max_kg") ?? "").trim() || null,
        output_value: String(formData.get("output_value") ?? "").trim() || null,
        output_unit: String(formData.get("output_unit") ?? "mg"),
      },
    });
    revalidatePath(`/products/${productId}`, "page");
    return { ok: true, message: "Regla de dosis agregada." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}

export async function publishDosingAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin"]);
    const productId = String(formData.get("product_id") ?? "");
    const profileId = String(formData.get("profile_id") ?? "");
    await apiRequest(`/products/${productId}/dosing/profiles/${profileId}/publish`, {
      method: "POST",
    });
    revalidatePath(`/products/${productId}`);
    return { ok: true, message: "Dosis publicada." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}

export async function importComparisonAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin", "scientist"]);
    const productId = String(formData.get("product_id") ?? "");
    const file = formData.get("file");
    if (!productId) return { ok: false, message: "Falta producto." };
    if (!(file instanceof File) || file.size === 0) {
      return { ok: false, message: "Seleccioná un archivo Excel." };
    }
    const token = await getAccessToken();
    if (!token) return { ok: false, message: "Sesión no válida." };
    const upstream = new FormData();
    upstream.set("file", file);
    const response = await fetch(
      `${getApiBaseUrl()}/products/${productId}/comparison/import`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: upstream,
        cache: "no-store",
      },
    );
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text.slice(0, 400) || "Import falló");
    }
    revalidatePath(`/products/${productId}`);
    return { ok: true, message: "Comparativa importada (borrador)." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}

export async function publishComparisonAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin"]);
    const productId = String(formData.get("product_id") ?? "");
    await apiRequest(`/products/${productId}/comparison/publish`, { method: "POST" });
    revalidatePath(`/products/${productId}`);
    return { ok: true, message: "Comparativa publicada." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}

export async function saveComparisonColumnsAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    await requireRole(["admin", "scientist"]);
    const productId = String(formData.get("product_id") ?? "");
    if (!productId) return { ok: false, message: "Falta producto." };
    const priorityKeys = formData
      .getAll("priority_column_keys")
      .map((v) => String(v))
      .filter(Boolean);
    await apiRequest(`/products/${productId}/comparison/columns`, {
      method: "PUT",
      json: { priority_column_keys: priorityKeys },
    });
    revalidatePath(`/products/${productId}`);
    return { ok: true, message: "Prioridades guardadas." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}
