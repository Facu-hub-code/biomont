"use client";

import Link, { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";

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

function NavLinkLabel({ label }: { label: string }) {
  const { pending } = useLinkStatus();

  return (
    <>
      {pending ? (
        <span
          className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-slate-300 border-t-biomont-primary"
          aria-hidden
        />
      ) : null}
      <span className={pending ? "opacity-70" : undefined}>{label}</span>
    </>
  );
}

function NavItem({ href, label }: { href: string; label: string }) {
  const pathname = usePathname();
  const isActive =
    pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));

  return (
    <Link href={href} className={isActive ? "nav-link-active" : "nav-link-inactive"}>
      <NavLinkLabel label={label} />
    </Link>
  );
}

export function DashboardNav() {
  return (
    <nav className="flex flex-col gap-0.5">
      {NAV_ITEMS.map((item) => (
        <NavItem key={item.href} href={item.href} label={item.label} />
      ))}
    </nav>
  );
}
