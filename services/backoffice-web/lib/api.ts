import { cookies } from "next/headers";

const SESSION_COOKIE = "biomont_session";

export type ApiInit = RequestInit & {
  authenticated?: boolean;
  json?: unknown;
};

/** Base URL for API calls. Browser uses NEXT_PUBLIC_*; SSR/server actions use API_INTERNAL_BASE_URL when set (Docker service hostname). */
export function getApiBaseUrl(): string {
  const publicBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8002";
  if (typeof window === "undefined") {
    const internal = process.env.API_INTERNAL_BASE_URL?.trim();
    return internal || publicBase;
  }
  return publicBase;
}

export async function getAccessToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(SESSION_COOKIE)?.value ?? null;
}

export async function setSessionCookie(token: string, maxAgeSeconds: number): Promise<void> {
  const store = await cookies();
  const secure =
    process.env.SESSION_COOKIE_SECURE === "true"
      ? true
      : process.env.SESSION_COOKIE_SECURE === "false"
        ? false
        : process.env.NODE_ENV === "production";
  store.set({
    name: SESSION_COOKIE,
    value: token,
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: maxAgeSeconds,
    secure,
  });
}

export async function clearSessionCookie(): Promise<void> {
  const store = await cookies();
  store.delete(SESSION_COOKIE);
}

export async function apiRequest<T = unknown>(path: string, init: ApiInit = {}): Promise<T> {
  const headers = new Headers(init.headers ?? {});
  let body: BodyInit | undefined = init.body ?? undefined;
  if (init.json !== undefined) {
    body = JSON.stringify(init.json);
    headers.set("Content-Type", "application/json");
  }
  if (init.authenticated !== false) {
    const token = await getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
    body,
    cache: "no-store",
  });
  if (response.status === 204) return undefined as unknown as T;
  const text = await response.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!response.ok) {
    const detail = (data && (data.detail ?? data.message)) ?? response.statusText;
    throw new Error(typeof detail === "string" ? detail : "request failed");
  }
  return data as T;
}
