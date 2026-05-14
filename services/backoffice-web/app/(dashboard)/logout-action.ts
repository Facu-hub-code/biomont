"use server";

import { redirect } from "next/navigation";

import { clearSessionCookie } from "@/lib/api";

export async function logoutAction() {
  await clearSessionCookie();
  redirect("/login");
}
