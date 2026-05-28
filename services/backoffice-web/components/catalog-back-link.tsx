import Link from "next/link";

import { ArrowLeft } from "lucide-react";

type Props = {
  href: string;
  label: string;
};

export function CatalogBackLink({ href, label }: Props) {
  return (
    <Link
      href={href}
      className="mb-4 inline-flex items-center gap-2 text-sm font-semibold text-teal-700 transition hover:text-teal-900"
      aria-label={label}
    >
      <ArrowLeft className="h-4 w-4 shrink-0" aria-hidden />
      {label}
    </Link>
  );
}
