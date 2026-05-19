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
        <aside className="flex w-64 shrink-0 flex-col border-r border-slate-200/80 bg-white shadow-sm">
          <div className="border-b border-slate-100 p-6">
            <h1 className="text-xl font-semibold tracking-tight text-biomont-primary">Biomont</h1>
            <p className="text-xs text-slate-500">Backoffice</p>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <DashboardNav />
          </div>
          <div className="border-t border-slate-100 p-4">
            <p className="mb-2 text-xs text-slate-500">
              {user.name} ({user.role})
            </p>
            <LogoutForm />
          </div>
        </aside>
        <main className="flex-1 overflow-y-auto bg-slate-50/50 p-8">{children}</main>
      </div>
    </ToastProvider>
  );
}
