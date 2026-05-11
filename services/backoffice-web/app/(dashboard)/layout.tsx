import Link from "next/link";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { clearSessionCookie } from "@/lib/api";
import { requireUser } from "@/lib/auth";

async function logoutAction() {
  "use server";
  await clearSessionCookie();
  redirect("/login");
}

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/documents", label: "Documentos" },
  { href: "/rtcs", label: "RTCs" },
  { href: "/prompts", label: "System prompt" },
  { href: "/tickets", label: "Tickets" },
];

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const user = await requireUser();
  return (
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
        <form action={logoutAction} className="mt-8">
          <p className="mb-2 text-xs text-slate-500">
            {user.name} ({user.role})
          </p>
          <button type="submit" className="btn-secondary w-full text-sm">
            Cerrar sesion
          </button>
        </form>
      </aside>
      <section className="flex-1 overflow-y-auto p-8">{children}</section>
    </div>
  );
}
