"use server";

import { redirect } from "next/navigation";

import { apiRequest, setSessionCookie } from "@/lib/api";

type LoginResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in_seconds: number;
};

export async function loginAction(formData: FormData) {
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
