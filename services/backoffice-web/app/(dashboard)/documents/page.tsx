import Link from "next/link";
import { revalidatePath } from "next/cache";

import { apiRequest, getApiBaseUrl } from "@/lib/api";

type Document = {
  id: string;
  title: string;
  product_name: string | null;
  country_iso: string | null;
  status: string;
  chunk_count: number;
  updated_at: string;
};

async function uploadDocumentAction(formData: FormData) {
  "use server";

  const apiBase = getApiBaseUrl();
  const { cookies } = await import("next/headers");
  const store = await cookies();
  const token = store.get("biomont_session")?.value;
  if (!token) {
    // #region agent log
    fetch("http://127.0.0.1:7513/ingest/a21c9983-9408-402f-b42a-56ff93d3e6ac", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "33ab56" },
      body: JSON.stringify({
        sessionId: "33ab56",
        runId: "pre-fix",
        hypothesisId: "H5",
        location: "documents/page.tsx:uploadDocumentAction",
        message: "no session token, action returns early",
        data: {},
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion
    return;
  }

  const upstream = new FormData();
  upstream.set("file", formData.get("file") as File);
  upstream.set("title", String(formData.get("title") ?? ""));
  const productName = formData.get("product_name");
  if (productName) upstream.set("product_name", String(productName));
  const country = formData.get("country_iso");
  if (country) upstream.set("country_iso", String(country));
  upstream.set("language", String(formData.get("language") ?? "es"));

  const response = await fetch(`${apiBase}/documents`, {
    method: "POST",
    body: upstream,
    headers: { Authorization: `Bearer ${token}` },
  });
  // #region agent log
  fetch("http://127.0.0.1:7513/ingest/a21c9983-9408-402f-b42a-56ff93d3e6ac", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "33ab56" },
    body: JSON.stringify({
      sessionId: "33ab56",
      runId: "pre-fix",
      hypothesisId: "H2",
      location: "documents/page.tsx:uploadDocumentAction",
      message: "POST /documents response",
      data: { status: response.status, ok: response.ok, apiBaseHost: (() => { try { return new URL(apiBase).host; } catch { return "invalid"; } })() },
      timestamp: Date.now(),
    }),
  }).catch(() => {});
  // #endregion
  if (!response.ok) {
    const text = await response.text();
    // #region agent log
    fetch("http://127.0.0.1:7513/ingest/a21c9983-9408-402f-b42a-56ff93d3e6ac", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "33ab56" },
      body: JSON.stringify({
        sessionId: "33ab56",
        runId: "pre-fix",
        hypothesisId: "H2",
        location: "documents/page.tsx:uploadDocumentAction",
        message: "POST /documents error body preview",
        data: { status: response.status, bodyPreview: text.slice(0, 300) },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion
    throw new Error(text || `upload failed (${response.status})`);
  }
  revalidatePath("/documents");
  // #region agent log
  fetch("http://127.0.0.1:7513/ingest/a21c9983-9408-402f-b42a-56ff93d3e6ac", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "33ab56" },
    body: JSON.stringify({
      sessionId: "33ab56",
      runId: "pre-fix",
      hypothesisId: "H2",
      location: "documents/page.tsx:uploadDocumentAction",
      message: "upload ok, revalidatePath done",
      data: {},
      timestamp: Date.now(),
    }),
  }).catch(() => {});
  // #endregion
}

export default async function DocumentsPage() {
  let documents: Document[] = [];
  try {
    const raw = await apiRequest<Document[]>("/documents");
    if (!Array.isArray(raw)) {
      console.error(
        "[bm-debug-33ab56]",
        JSON.stringify({
          hypothesisId: "H1",
          message: "GET /documents not an array",
          typeofPayload: typeof raw,
          keys:
            raw && typeof raw === "object" ? Object.keys(raw as object).slice(0, 20) : null,
        }),
      );
      throw new Error("El API devolvió un formato inesperado al listar documentos.");
    }
    documents = raw;
    // #region agent log
    const first = documents[0];
    fetch("http://127.0.0.1:7513/ingest/a21c9983-9408-402f-b42a-56ff93d3e6ac", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "33ab56" },
      body: JSON.stringify({
        sessionId: "33ab56",
        runId: "pre-fix",
        hypothesisId: "H1",
        location: "documents/page.tsx:DocumentsPage",
        message: "GET /documents ok",
        data: {
          isArray: Array.isArray(documents),
          length: documents.length,
          firstUpdatedAt: first?.updated_at ?? null,
          firstId: first?.id ?? null,
        },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion
  } catch (err) {
    // #region agent log
    fetch("http://127.0.0.1:7513/ingest/a21c9983-9408-402f-b42a-56ff93d3e6ac", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "33ab56" },
      body: JSON.stringify({
        sessionId: "33ab56",
        runId: "pre-fix",
        hypothesisId: "H1",
        location: "documents/page.tsx:DocumentsPage",
        message: "GET /documents failed",
        data: { err: err instanceof Error ? err.message : String(err) },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion
    throw err;
  }
  // #region agent log
  fetch("http://127.0.0.1:7513/ingest/a21c9983-9408-402f-b42a-56ff93d3e6ac", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "33ab56" },
    body: JSON.stringify({
      sessionId: "33ab56",
      runId: "pre-fix",
      hypothesisId: "H4",
      location: "documents/page.tsx:DocumentsPage",
      message: "before render table",
      data: {
        sampleDatesOk: documents.every((d) => {
          const t = Date.parse(d.updated_at);
          return !Number.isNaN(t);
        }),
      },
      timestamp: Date.now(),
    }),
  }).catch(() => {});
  // #endregion
  return (
    <div className="space-y-8">
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">Documentos</h2>
        <p className="text-sm text-slate-500">
          Subi un PDF y lo procesamos con docling para alimentar el RAG.
        </p>
      </header>

      <form action={uploadDocumentAction} className="card grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <label className="form-label" htmlFor="file">
            Archivo PDF
          </label>
          <input
            id="file"
            name="file"
            type="file"
            accept="application/pdf"
            required
            className="form-input"
          />
        </div>
        <div>
          <label className="form-label" htmlFor="title">Titulo</label>
          <input id="title" name="title" required className="form-input" />
        </div>
        <div>
          <label className="form-label" htmlFor="product_name">Producto</label>
          <input id="product_name" name="product_name" className="form-input" />
        </div>
        <div>
          <label className="form-label" htmlFor="country_iso">
            Pais (iso2, vacio = global)
          </label>
          <input
            id="country_iso"
            name="country_iso"
            maxLength={2}
            className="form-input uppercase"
          />
        </div>
        <div>
          <label className="form-label" htmlFor="language">Idioma</label>
          <input id="language" name="language" defaultValue="es" maxLength={2} className="form-input" />
        </div>
        <div className="md:col-span-2">
          <button type="submit" className="btn-primary">
            Procesar y validar
          </button>
        </div>
      </form>

      <table className="table-default">
        <thead>
          <tr>
            <th>Titulo</th>
            <th>Producto</th>
            <th>Pais</th>
            <th>Status</th>
            <th>Chunks</th>
            <th>Actualizado</th>
            <th />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {documents.map((doc) => (
            <tr key={doc.id}>
              <td className="font-medium">{doc.title}</td>
              <td>{doc.product_name ?? "-"}</td>
              <td>{doc.country_iso ?? "GLOBAL"}</td>
              <td>
                <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium uppercase">
                  {doc.status}
                </span>
              </td>
              <td>{doc.chunk_count}</td>
              <td>{new Date(doc.updated_at).toLocaleString()}</td>
              <td>
                <Link href={`/documents/${doc.id}`} className="text-biomont-primary hover:underline">
                  Ver markdown
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
