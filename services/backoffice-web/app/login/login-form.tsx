"use client";

import { Sparkles } from "lucide-react";
import { useFormStatus } from "react-dom";

import { loginAction } from "./actions";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      className="btn-primary w-full justify-center py-3 text-[15px] disabled:cursor-wait"
      disabled={pending}
      aria-busy={pending}
    >
      {pending ? (
        <span className="inline-flex items-center justify-center gap-2">
          <span
            className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-white border-t-transparent"
            aria-hidden
          />
          Entrando…
        </span>
      ) : (
        <>
          Entrar al workspace
          <Sparkles className="h-4 w-4 opacity-90" aria-hidden />
        </>
      )}
    </button>
  );
}

function PendingFieldset({ children }: { children: React.ReactNode }) {
  const { pending } = useFormStatus();
  return (
    <fieldset
      disabled={pending}
      className="min-w-0 space-y-5 border-0 p-0 disabled:[&_input]:cursor-wait"
    >
      {children}
    </fieldset>
  );
}

export function LoginForm({ error }: { error?: string }) {
  return (
    <form
      action={loginAction}
      className="relative w-full max-w-[420px] space-y-6 rounded-[28px] border border-white/70 bg-white/75 p-8 shadow-[0_24px_80px_-24px_rgba(15,76,92,0.35)] backdrop-blur-2xl md:p-10"
    >
      <header className="space-y-3 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-biomont-primary to-teal-600 text-xl font-bold text-white shadow-lift ring-4 ring-white/80">
          B
        </div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Biomont Ops</h1>
          <p className="mt-2 text-sm leading-relaxed text-zinc-500">
            Consola AI-native para catálogo, documentos y conversaciones del agente veterinario.
          </p>
        </div>
      </header>
      <PendingFieldset>
        <div>
          <label className="form-label" htmlFor="email">
            Email corporativo
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            className="form-input"
          />
        </div>
        <div>
          <label className="form-label" htmlFor="password">
            Contraseña
          </label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            className="form-input"
          />
        </div>
      </PendingFieldset>
      {error ? (
        <p className="rounded-2xl border border-red-200/90 bg-red-50/95 px-4 py-3 text-center text-sm font-medium text-red-900">
          {error}
        </p>
      ) : null}
      <SubmitButton />
      <p className="text-center text-[11px] font-medium uppercase tracking-wider text-zinc-400">
        Acceso restringido · uso interno Biomont
      </p>
    </form>
  );
}
