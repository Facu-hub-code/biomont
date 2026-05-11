import { redirect } from "next/navigation";

import { apiRequest, getAccessToken } from "./api";

export type CurrentUser = {
  id: string;
  email: string;
  name: string;
  role: "admin" | "scientist" | "viewer";
};

export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  const token = await getAccessToken();
  if (!token) return null;
  try {
    return await apiRequest<CurrentUser>("/auth/me");
  } catch (_) {
    return null;
  }
}

export async function requireUser(): Promise<CurrentUser> {
  const user = await fetchCurrentUser();
  if (!user) redirect("/login");
  return user;
}

export async function requireRole(roles: CurrentUser["role"][]): Promise<CurrentUser> {
  const user = await requireUser();
  if (!roles.includes(user.role)) redirect("/dashboard");
  return user;
}
