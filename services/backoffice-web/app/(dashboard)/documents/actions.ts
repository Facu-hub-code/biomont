"use server";

import { revalidatePath } from "next/cache";

import { getApiBaseUrl, getAccessToken } from "@/lib/api";
import { formatApiError, parseErrorBodyText } from "@/lib/api-error";
import type { ActionFeedbackState } from "@/lib/form-action-state";

export async function uploadDocumentAction(
  _prev: ActionFeedbackState | null,
  formData: FormData,
): Promise<ActionFeedbackState> {
  try {
    const apiBase = getApiBaseUrl();
    const token = await getAccessToken();
    if (!token) {
      return { ok: false, message: "Sesión no válida. Volvé a iniciar sesión." };
    }

    const file = formData.get("file");
    if (!(file instanceof File) || file.size === 0) {
      return { ok: false, message: "Seleccioná un archivo PDF." };
    }

    const upstream = new FormData();
    upstream.set("file", file);
    upstream.set("title", String(formData.get("title") ?? ""));
    const productIds = formData.getAll("product_ids").map(String).filter(Boolean);
    for (const pid of productIds) {
      upstream.append("product_ids", pid);
    }
    const productId = String(formData.get("product_id") ?? "").trim();
    if (productId && !productIds.includes(productId)) {
      upstream.set("product_id", productId);
    } else if (productIds.length > 0) {
      upstream.set("product_id", productIds[0]);
    }
    const productName = formData.get("product_name");
    if (productName && String(productName).trim()) {
      upstream.set("product_name", String(productName));
    }
    const country = formData.get("country_iso");
    if (country) upstream.set("country_iso", String(country));
    upstream.set("language", String(formData.get("language") ?? "es"));
    upstream.set("kind", String(formData.get("kind") ?? "bitacora"));

    const response = await fetch(`${apiBase}/documents`, {
      method: "POST",
      body: upstream,
      headers: { Authorization: `Bearer ${token}` },
    });

    const text = await response.text();
    if (!response.ok) {
      return { ok: false, message: parseErrorBodyText(text) || `Error ${response.status}` };
    }

    revalidatePath("/documents");
    return { ok: true, message: "Documento enviado para procesamiento." };
  } catch (e) {
    return { ok: false, message: formatApiError(e) };
  }
}
