"use client";

import { useFormStatus } from "react-dom";

import { loginAction } from "./actions";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      className="btn-primary w-full disabled:cursor-wait"
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
        "Entrar"
      )}
    </button>
  );
}

function PendingFieldset({ children }: { children: React.ReactNode }) {
  const { pending } = useFormStatus();
  return (
    <fieldset
      disabled={pending}
      className="min-w-0 space-y-4 border-0 p-0 disabled:[&_input]:cursor-wait"
    >
      {children}
    </fieldset>
  );
}

export function LoginForm({ error }: { error?: string }) {
  return (
    <form action={loginAction} className="card w-full max-w-md space-y-4">
      <header>
        <h1 className="text-2xl font-semibold text-biomont-primary">Biomont</h1>
        <p className="text-sm text-slate-500">Acceso al backoffice</p>
      </header>
      <PendingFieldset>
        <div>
          <label className="form-label" htmlFor="email">
            Email
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
            Password
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
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      ) : null}
      <SubmitButton />
    </form>
  );
}
