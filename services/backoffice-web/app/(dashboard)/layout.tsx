import Link from "next/link";
import type { ReactNode } from "react";

import { ToastProvider } from "@/components/toast-provider";
import { requireUser } from "@/lib/auth";

import { LogoutForm } from "./logout-form";

/** Rutas autenticadas deben leer la cookie de sesión en cada request (evita RSC estático sin token). */
export const dynamic = "force-dynamic";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/conversations", label: "Chats" },
  { href: "/documents", label: "Documentos" },
  { href: "/products", label: "Productos" },
  { href: "/agent-decisions", label: "Decisiones del agente" },
  { href: "/rtcs", label: "RTCs" },
  { href: "/prompts", label: "System prompt" },
  { href: "/tickets", label: "Tickets" },
];

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const user = await requireUser();
  return (
    <ToastProvider>
      <div className="flex min-h-screen">
        <aside className="w-64 shrink-0 border-r border-slate-200 bg-white p-6">
          <div className="mb-8">
            <h1 className="text-xl font-semibold text-biomont-primary">Biomont</h1>
            <p className="text-xs text-slate-500">Backoffice</p>
          </div>
          <nav className="flex flex-col gap-1">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-md px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <p className="mb-2 mt-8 text-xs text-slate-500">
            {user.name} ({user.role})
          </p>
          <LogoutForm />
        </aside>
        <section className="flex-1 overflow-y-auto p-8">{children}</section>
      </div>
    </ToastProvider>
  );
}
