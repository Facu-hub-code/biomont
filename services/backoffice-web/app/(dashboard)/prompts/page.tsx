import { History, Sparkles } from "lucide-react";

import { ActionFeedbackForm } from "@/components/action-feedback-form";
import { SubmitButton } from "@/components/submit-button";
import { apiRequest } from "@/lib/api";

import { activatePromptAction, createPromptAction } from "./actions";

type SystemPrompt = {
  id: string;
  version: number;
  content: string;
  is_active: boolean;
  created_at: string;
};

export default async function SystemPromptsPage() {
  const prompts = await apiRequest<SystemPrompt[]>("/system-prompts");
  const active = prompts.find((p) => p.is_active);
  return (
    <div className="space-y-10">
      <header className="page-header">
        <h2 className="page-title">System prompt</h2>
        <p className="page-subtitle">
          La versión activa viaja en cada turno del agente (TTL de cache ~60s en runtime).
        </p>
      </header>

      <section className="card-static overflow-hidden border-teal-500/15 bg-gradient-to-br from-white via-teal-50/25 to-white p-0 shadow-glow">
        <div className="flex items-center gap-3 border-b border-teal-900/[0.06] bg-white/70 px-6 py-4 backdrop-blur-md">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-600 to-biomont-primary text-white shadow-lg">
            <Sparkles className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-teal-700">Activo en producción</p>
            <p className="text-lg font-semibold tracking-tight text-zinc-900">Versión v{active?.version ?? "—"}</p>
          </div>
        </div>
        <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap bg-zinc-950/[0.03] p-6 font-mono text-sm leading-relaxed text-zinc-800">
          {active?.content ?? "(sin prompt activo)"}
        </pre>
      </section>

      <ActionFeedbackForm action={createPromptAction} successMessage="Nueva versión del prompt guardada.">
        <div className="card-static space-y-4 border-white/90">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-zinc-800">
            <span className="rounded-lg bg-zinc-900 px-2 py-1 font-mono text-[11px] text-white">NEW</span>
            Nueva versión
          </h3>
          <textarea
            name="content"
            required
            rows={12}
            className="form-input font-mono text-sm leading-relaxed"
            placeholder="Sos el asistente de productos veterinarios de Biomont..."
          />
          <SubmitButton label="Guardar y activar" pendingLabel="Guardando…" />
        </div>
      </ActionFeedbackForm>

      <section>
        <h3 className="mb-5 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-zinc-400">
          <History className="h-4 w-4 text-zinc-400" aria-hidden />
          Historial
        </h3>
        <ul className="grid gap-4">
          {prompts.map((prompt) => (
            <li key={prompt.id} className="card-static flex flex-col gap-4 border-white/90 p-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-lg font-bold text-zinc-900">v{prompt.version}</span>
                  {prompt.is_active ? (
                    <span className="badge rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-bold uppercase tracking-wide text-emerald-900 ring-1 ring-emerald-400/15">
                      Activo
                    </span>
                  ) : (
                    <span className="badge-neutral text-[11px] font-semibold uppercase tracking-wide">
                      Archivado
                    </span>
                  )}
                  <span className="text-xs font-medium text-zinc-400">
                    {new Date(prompt.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="line-clamp-3 font-mono text-sm leading-relaxed text-zinc-600">{prompt.content}</p>
              </div>
              {!prompt.is_active ? (
                <ActionFeedbackForm
                  action={activatePromptAction}
                  successMessage={`Prompt v${prompt.version} activado.`}
                >
                  <input type="hidden" name="version" value={prompt.version} />
                  <SubmitButton label="Activar esta versión" pendingLabel="Activando…" variant="secondary" />
                </ActionFeedbackForm>
              ) : null}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
