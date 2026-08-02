// backend-proxy — server→server forwarding from Next route handlers to FastAPI.
//
// Phase 4 (Cụm B/C): as business logic moves into FastAPI, a Next route becomes a
// thin proxy. Unlike the older brief/patients proxies, this forwards the caller's
// Supabase access token (Authorization: Bearer …) so the backend can verify
// identity → staff → role (server-authoritative, identity.py), in addition to the
// shared X-API-Key.
//
// The cutover is finished: every business route proxies unconditionally, the
// per-route *_VIA_BACKEND flags are gone, and no route holds a legacy
// direct-Supabase branch to fall back to. CLINIC_API_URL not being set is now a
// broken deployment rather than a supported mode, so it fails loudly.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "./supabase-server";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

/**
 * Forward a JSON body to a FastAPI endpoint, attaching the caller's Supabase
 * access token (Bearer) + the shared X-API-Key, and mirror the backend's
 * status/body back to the browser as the { ok } / { error } shape the UI expects.
 *
 * `extraHeaders` is for headers the route handler decides to send — today only
 * `Idempotency-Key`, which has to come from the browser (a key minted here would
 * be new on every retry, which is the one thing an idempotency key must not be).
 * The route names the headers explicitly; nothing forwards a client header list
 * wholesale, so a caller cannot smuggle in Authorization or X-Clinic-ID.
 */
export async function proxyJsonToBackend(
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body: unknown,
  extraHeaders?: Record<string, string>,
): Promise<NextResponse> {
  if (!API_BASE) {
    // Previously a flag returned false here and the route quietly used its
    // legacy branch. There is no legacy branch now, so an unset CLINIC_API_URL
    // must say so instead of failing as a confusing 502 per request.
    return NextResponse.json(
      { error: "CLINIC_API_URL chưa được cấu hình trên server." },
      { status: 503 },
    );
  }
  const supabase = await getSupabaseServer();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) {
    return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  }

  // Extras go in first, then the identity headers overwrite them: whatever a
  // route passes, it cannot end up replacing the caller's own token.
  const headers: Record<string, string> = {};
  for (const [name, value] of Object.entries(extraHeaders ?? {})) {
    if (value) headers[name] = value;
  }
  headers["Content-Type"] = "application/json";
  headers.Authorization = `Bearer ${token}`;
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { error: "Không kết nối được máy chủ xử lý" },
      { status: 502 },
    );
  }

  const text = await res.text();
  let payload: unknown = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { error: text || "Lỗi máy chủ" };
  }
  // FastAPI domain errors come back as { error, message }; surface `message` to the UI.
  if (
    !res.ok &&
    payload &&
    typeof payload === "object" &&
    "message" in payload
  ) {
    const msg = (payload as { message?: string }).message;
    return NextResponse.json({ error: msg ?? "Lỗi xử lý" }, { status: res.status });
  }
  return NextResponse.json(payload, { status: res.status });
}

/** Server-side GET from FastAPI, with the caller's own token.
 *
 * proxyJsonToBackend is for route handlers, which return a NextResponse. A
 * server component wants the data. Both go through the caller's token rather
 * than the shared key alone, so the backend resolves the same identity — and
 * the same clinic — that the page was rendered for.
 *
 * Returns null when there is no session or the backend refuses. Callers render
 * the page without the extra detail rather than failing: these are progress
 * indicators, not the reason the screen exists.
 */
export async function fetchFromBackend<T>(path: string): Promise<T | null> {
  if (!API_BASE) return null;

  const supabase = await getSupabaseServer();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) return null;

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  try {
    const res = await fetch(`${API_BASE}${path}`, { headers, cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
