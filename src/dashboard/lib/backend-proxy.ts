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
import { getStaffContext } from "./current-staff";
import { getSupabaseServer } from "./supabase-server";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

/**
 * Forward a JSON body to a FastAPI endpoint, attaching the caller's Supabase
 * access token (Bearer) + the shared X-API-Key, and mirror the backend's
 * status/body back to the browser as the { ok } / { error } shape the UI expects.
 *
 * Also attaches X-Clinic-ID. The backend has asked for it since W3 — without
 * it, identity.py finds two active memberships, cannot tell which one the
 * request means, and refuses (403). Nothing here ever sent it, so a doctor
 * working at two clinics could not use the product at all.
 */
export async function proxyJsonToBackend(
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body: unknown,
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

  const context = await getStaffContext();
  if (context.status === "must_choose_clinic") {
    // The layout sends people to the picker before they can click anything, so
    // reaching here means a stale tab. Say which of the two problems it is
    // rather than let the backend's generic 403 read as "no permission".
    return NextResponse.json(
      { error: "Chưa chọn phòng khám đang làm việc." },
      { status: 409 },
    );
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;
  // Sent from the resolved membership, not straight from the cookie: a stale
  // selector must not make this side and identity.py disagree about the tenant.
  if (context.status === "resolved") {
    headers["X-Clinic-ID"] = context.staff.clinic_id;
  }

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
  const context = await getStaffContext();
  if (context.status === "resolved") {
    headers["X-Clinic-ID"] = context.staff.clinic_id;
  }

  try {
    const res = await fetch(`${API_BASE}${path}`, { headers, cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
