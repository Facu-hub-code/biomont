"use client";

import {
  BrainCircuit,
  FileStack,
  LayoutDashboard,
  LifeBuoy,
  MessagesSquare,
  Package,
  Scale,
  Smartphone,
  Settings2,
  Sparkles,
  Terminal,
} from "lucide-react";
import Link, { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS: { href: string; label: string; icon: typeof LayoutDashboard }[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/conversations", label: "Chats", icon: MessagesSquare },
  { href: "/documents", label: "Documentos", icon: FileStack },
  { href: "/products", label: "Productos", icon: Package },
  { href: "/competitors", label: "Competidores", icon: Scale },
  { href: "/agent-decisions", label: "Decisiones IA", icon: BrainCircuit },
  { href: "/rtcs", label: "RTCs", icon: Smartphone },
  { href: "/prompts", label: "System prompt", icon: Terminal },
  { href: "/agent-config", label: "Config. agente", icon: Settings2 },
  { href: "/tickets", label: "Tickets", icon: LifeBuoy },
];

function NavLinkLabel({
  label,
  Icon,
}: {
  label: string;
  Icon: typeof LayoutDashboard;
}) {
  const { pending } = useLinkStatus();

  return (
    <>
      <Icon
        className={`h-[18px] w-[18px] shrink-0 opacity-70 transition-opacity duration-200 ${pending ? "opacity-40" : "group-hover:opacity-100"}`}
        aria-hidden
      />
      <span className={`min-w-0 flex-1 truncate ${pending ? "opacity-70" : ""}`}>
        {label}
      </span>
      {pending ? (
        <span
          className="ml-auto h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-teal-600/25 border-t-teal-600"
          aria-hidden
        />
      ) : null}
    </>
  );
}

function NavItem({
  href,
  label,
  icon,
}: {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
}) {
  const pathname = usePathname();
  const isActive =
    pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));

  return (
    <Link
      href={href}
      className={`group flex ${isActive ? "nav-link-active" : "nav-link-inactive"}`}
    >
      <NavLinkLabel label={label} Icon={icon} />
    </Link>
  );
}

export function DashboardNav() {
  return (
    <nav className="flex flex-col gap-1">
      <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
        Workspace
      </p>
      {NAV_ITEMS.map((item) => (
        <NavItem key={item.href} href={item.href} label={item.label} icon={item.icon} />
      ))}
      <div className="mt-6 rounded-2xl border border-teal-600/10 bg-gradient-to-br from-teal-600/[0.07] to-transparent p-4 shadow-sm ring-1 ring-white/60">
        <div className="flex items-start gap-2">
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-teal-600" aria-hidden />
          <div>
            <p className="text-xs font-semibold text-zinc-800">Agente veterinario</p>
            <p className="mt-1 text-[11px] leading-snug text-zinc-500">
              RAG + WhatsApp en vivo. Auditá decisiones en Decisiones IA.
            </p>
          </div>
        </div>
      </div>
    </nav>
  );
}
