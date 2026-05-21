import type { ReactNode } from "react";

import { DashboardNav } from "@/components/dashboard-nav";
import { ToastProvider } from "@/components/toast-provider";
import { requireUser } from "@/lib/auth";

import { LogoutForm } from "./logout-form";

/** Rutas autenticadas deben leer la cookie de sesión en cada request (evita RSC estático sin token). */
export const dynamic = "force-dynamic";

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const user = await requireUser();
  return (
    <ToastProvider>
      <div className="flex min-h-screen">
        <aside className="sticky top-0 flex h-screen w-[272px] shrink-0 flex-col border-r border-zinc-200/80 bg-white/70 px-5 py-8 shadow-[8px_0_40px_-28px_rgba(15,76,92,0.35)] backdrop-blur-xl">
          <div className="mb-8 px-1">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-biomont-primary to-teal-700 text-lg font-bold text-white shadow-lift ring-2 ring-white/70">
                B
              </div>
              <div>
                <h1 className="text-lg font-semibold tracking-tight text-zinc-900">Biomont</h1>
                <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                  Ops · IA
                </p>
              </div>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto pb-4 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            <DashboardNav />
          </div>
          <div className="border-t border-zinc-200/70 pt-5">
            <p className="mb-3 truncate px-1 text-xs font-medium text-zinc-600">
              {user.name}
              <span className="mt-0.5 block text-[11px] font-normal capitalize text-zinc-400">
                {user.role}
              </span>
            </p>
            <LogoutForm />
          </div>
        </aside>
        <main className="relative flex-1 overflow-y-auto">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(20,184,166,0.09),transparent)]" />
          <div className="relative mx-auto max-w-[1440px] px-6 py-10 md:px-10">{children}</div>
        </main>
      </div>
    </ToastProvider>
  );
}
