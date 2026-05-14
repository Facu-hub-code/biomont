import { cookies } from "next/headers";

import { formatFastApiDetail } from "@/lib/api-error";

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
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : undefined;
  } catch {
    // #region agent log
    fetch("http://127.0.0.1:7513/ingest/a21c9983-9408-402f-b42a-56ff93d3e6ac", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "33ab56" },
      body: JSON.stringify({
        sessionId: "33ab56",
        runId: "pre-fix",
        hypothesisId: "H3",
        location: "lib/api.ts:apiRequest",
        message: "JSON.parse failed",
        data: {
          path,
          status: response.status,
          textPreview: text.slice(0, 200),
        },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion
    throw new SyntaxError(`invalid JSON for ${path}`);
  }
  if (!response.ok) {
    const payload =
      typeof data === "object" && data !== null ? (data as Record<string, unknown>) : undefined;
    const raw = payload ? payload["detail"] ?? payload["message"] : undefined;
    const message =
      raw !== undefined && raw !== null
        ? formatFastApiDetail(raw)
        : text.trim()
          ? text.slice(0, 800)
          : response.statusText;
    throw new Error(message || "request failed");
  }
  return data as T;
}
