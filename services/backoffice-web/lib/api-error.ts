/**
 * Normaliza `detail` típico de FastAPI (string, lista de errores de validación, etc.).
 */
export function formatFastApiDetail(raw: unknown): string {
  if (raw == null) return "Solicitud rechazada";
  if (typeof raw === "string") return raw;
  if (Array.isArray(raw)) {
    const parts = raw.map((item) => {
      if (item && typeof item === "object" && "msg" in item) {
        const row = item as { loc?: unknown; msg: unknown };
        const loc =
          Array.isArray(row.loc) && row.loc.length
            ? `${row.loc.map(String).join(".")}: `
            : "";
        return `${loc}${String(row.msg)}`;
      }
      return typeof item === "string" ? item : JSON.stringify(item);
    });
    return parts.join(" · ");
  }
  if (typeof raw === "object" && "message" in (raw as object)) {
    return String((raw as { message: unknown }).message);
  }
  try {
    return JSON.stringify(raw);
  } catch {
    return "Error desconocido";
  }
}

export function formatApiError(error: unknown): string {
  if (error instanceof Error) return error.message.trim() || "Error";
  return String(error);
}

/** Cuerpo texto de error HTTP (p.ej. POST multipart) que puede ser JSON FastAPI o HTML. */
export function parseErrorBodyText(text: string): string {
  const t = text.trim();
  if (!t) return "Error en el servidor";
  try {
    const j = JSON.parse(t) as Record<string, unknown>;
    if (Object.prototype.hasOwnProperty.call(j, "detail")) {
      return formatFastApiDetail(j.detail);
    }
    if (typeof j.message === "string") return j.message;
  } catch {
    // no es JSON
  }
  return t.length > 500 ? `${t.slice(0, 500)}…` : t;
}
