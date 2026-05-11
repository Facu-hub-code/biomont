import { revalidatePath } from "next/cache";

import { apiRequest } from "@/lib/api";

type SystemPrompt = {
  id: string;
  version: number;
  content: string;
  is_active: boolean;
  created_at: string;
};

async function createPromptAction(formData: FormData) {
  "use server";
  const content = String(formData.get("content") ?? "").trim();
  if (!content) return;
  await apiRequest("/system-prompts", { method: "POST", json: { content } });
  revalidatePath("/prompts");
}

async function activatePromptAction(formData: FormData) {
  "use server";
  const version = Number(formData.get("version"));
  if (!Number.isInteger(version)) return;
  await apiRequest(`/system-prompts/${version}/activate`, { method: "POST" });
  revalidatePath("/prompts");
}

export default async function SystemPromptsPage() {
  const prompts = await apiRequest<SystemPrompt[]>("/system-prompts");
  const active = prompts.find((p) => p.is_active);
  return (
    <div className="space-y-8">
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">System prompt</h2>
        <p className="text-sm text-slate-500">
          La version activa se usa en cada respuesta del agente (cache 60s).
        </p>
      </header>

      <section className="card">
        <h3 className="mb-2 text-sm font-semibold text-slate-700">
          Version activa: v{active?.version ?? "-"}
        </h3>
        <pre className="whitespace-pre-wrap rounded-md bg-slate-50 p-4 text-sm text-slate-800">
{active?.content ?? "(sin prompt activo)"}
        </pre>
      </section>

      <form action={createPromptAction} className="card space-y-4">
        <h3 className="text-sm font-semibold text-slate-700">Crear nueva version</h3>
        <textarea
          name="content"
          required
          rows={10}
          className="form-input font-mono"
          placeholder="Eres el asistente de productos veterinarios de Biomont..."
        />
        <button type="submit" className="btn-primary">
          Guardar y activar
        </button>
      </form>

      <section>
        <h3 className="mb-3 text-sm font-semibold text-slate-700">Historial</h3>
        <table className="table-default">
          <thead>
            <tr>
              <th>Version</th>
              <th>Activo</th>
              <th>Creado</th>
              <th>Preview</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {prompts.map((prompt) => (
              <tr key={prompt.id}>
                <td>v{prompt.version}</td>
                <td>{prompt.is_active ? "si" : "no"}</td>
                <td>{new Date(prompt.created_at).toLocaleString()}</td>
                <td className="max-w-xl truncate text-slate-500">
                  {prompt.content.slice(0, 120)}...
                </td>
                <td>
                  {!prompt.is_active ? (
                    <form action={activatePromptAction}>
                      <input type="hidden" name="version" value={prompt.version} />
                      <button type="submit" className="text-biomont-primary hover:underline">
                        Activar
                      </button>
                    </form>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
