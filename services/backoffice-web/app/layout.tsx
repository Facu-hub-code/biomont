import type { Metadata } from "next";
import { DM_Mono, Plus_Jakarta_Sans } from "next/font/google";
import type { ReactNode } from "react";

import "./globals.css";

const sans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const mono = DM_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Biomont Backoffice",
  description: "Backoffice de productos veterinarios Biomont.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es" className={`${sans.variable} ${mono.variable}`}>
      <body className="min-h-screen bg-gradient-to-br from-zinc-100 via-zinc-50 to-teal-50/40 font-sans text-zinc-900 antialiased">
        {children}
      </body>
    </html>
  );
}
