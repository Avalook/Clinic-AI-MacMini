/**
 * Server-side reads for the order composer.
 *
 * Same tagged-union shape as the other boards: a service picker that renders
 * empty when the backend is unreachable would tell a doctor this clinic offers
 * nothing.
 */

import { getSupabaseServer } from "@/lib/supabase-server";

import type { CatalogueEntry } from "@/app/(dashboard)/doctor/orders/[visitId]/OrderComposer";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

export type CatalogueResult =
  | { ok: true; data: CatalogueEntry[] }
  | { ok: false; reason: "no-session" | "unreachable" | "refused" | "forbidden" };

async function authHeaders(): Promise<Record<string, string> | null> {
  const supabase = await getSupabaseServer();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) return null;
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;
  return headers;
}

export async function fetchCatalogue(): Promise<CatalogueResult> {
  if (!API_BASE) return { ok: false, reason: "unreachable" };
  const headers = await authHeaders();
  if (!headers) return { ok: false, reason: "no-session" };
  try {
    const res = await fetch(`${API_BASE}/api/v1/service-catalogue`, {
      headers,
      cache: "no-store",
    });
    if (res.status === 403) return { ok: false, reason: "forbidden" };
    if (!res.ok) return { ok: false, reason: "refused" };
    return { ok: true, data: (await res.json()) as CatalogueEntry[] };
  } catch {
    return { ok: false, reason: "unreachable" };
  }
}

/** The patient's name for the summary panel. Null is fine — it is a label. */
export async function fetchVisitPatient(visitId: string): Promise<string | null> {
  if (!API_BASE) return null;
  const headers = await authHeaders();
  if (!headers) return null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/visits/${visitId}/work-items`, {
      headers,
      cache: "no-store",
    });
    if (!res.ok) return null;
    const rows = (await res.json()) as { node_code: string }[];
    return rows.length > 0 ? "Lượt khám đang mở" : null;
  } catch {
    return null;
  }
}
