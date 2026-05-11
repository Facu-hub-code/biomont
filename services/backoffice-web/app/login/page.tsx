import { redirect } from "next/navigation";

import { apiRequest, setSessionCookie } from "@/lib/api";

type LoginResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in_seconds: number;
};

async function loginAction(formData: FormData) {
  "use server";

  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  if (!email || !password) return;

  const response = await apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    json: { email, password },
    authenticated: false,
  });
  await setSessionCookie(response.access_token, response.expires_in_seconds);
  redirect("/dashboard");
}

export default function LoginPage({
  searchParams,
}: {
  searchParams?: { error?: string };
}) {
  const error = searchParams?.error;
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <form action={loginAction} className="card w-full max-w-md space-y-4">
        <header>
          <h1 className="text-2xl font-semibold text-biomont-primary">Biomont</h1>
          <p className="text-sm text-slate-500">Acceso al backoffice</p>
        </header>
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
        {error ? (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        ) : null}
        <button type="submit" className="btn-primary w-full">
          Entrar
        </button>
      </form>
    </main>
  );
}
