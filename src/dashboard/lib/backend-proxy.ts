// backend-proxy — server→server forwarding from Next route handlers to FastAPI.
//
// Phase 4 (Cụm B/C): as business logic moves into FastAPI, a Next route becomes a
// thin proxy. Unlike the older brief/patients proxies, this forwards the caller's
// Supabase access token (Authorization: Bearer …) so the backend can verify
// identity → staff → role (server-authoritative, identity.py), in addition to the
// shared X-API-Key.
//
// Cutover is per-route and OFF by default via an env flag, so nothing changes in
// prod until per-staff logins (staff.auth_user_id) are rolled out and the flag is
// set. Until then the caller keeps its legacy direct-Supabase path.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "./supabase-server";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

/** True when the payment write path should be proxied to FastAPI. */
export function paymentViaBackend(): boolean {
  return process.env.PAYMENT_VIA_BACKEND === "1" && API_BASE !== "";
}

/** True when the care-episode lifecycle should be proxied to FastAPI (W5). */
export function episodeViaBackend(): boolean {
  return process.env.EPISODE_VIA_BACKEND === "1" && API_BASE !== "";
}

/** True when the lab order/result write path should be proxied to FastAPI (W5). */
export function labViaBackend(): boolean {
  return process.env.LAB_VIA_BACKEND === "1" && API_BASE !== "";
}

/** True when ultrasound measurements should be proxied to FastAPI (W5). */
export function ultrasoundViaBackend(): boolean {
  return process.env.ULTRASOUND_VIA_BACKEND === "1" && API_BASE !== "";
}

/** True when specialty exam forms should be proxied to FastAPI (W5). */
export function clinicalFormViaBackend(): boolean {
  return process.env.CLINICAL_FORM_VIA_BACKEND === "1" && API_BASE !== "";
}

/** True when services-worklist and sono-queue writes go to FastAPI (W5). */
export function serviceLogViaBackend(): boolean {
  return process.env.SERVICE_LOG_VIA_BACKEND === "1" && API_BASE !== "";
}

/** True when customer-care writes should be proxied to FastAPI (W5). */
export function cskhViaBackend(): boolean {
  return process.env.CSKH_VIA_BACKEND === "1" && API_BASE !== "";
}

/** True when clinical-record writes should be proxied to FastAPI (W5). */
export function clinicalRecordViaBackend(): boolean {
  return process.env.CLINICAL_RECORD_VIA_BACKEND === "1" && API_BASE !== "";
}

/**
 * Forward a JSON body to a FastAPI endpoint, attaching the caller's Supabase
 * access token (Bearer) + the shared X-API-Key, and mirror the backend's
 * status/body back to the browser as the { ok } / { error } shape the UI expects.
 */
export async function proxyJsonToBackend(
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body: unknown,
): Promise<NextResponse> {
  const supabase = await getSupabaseServer();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) {
    return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
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
