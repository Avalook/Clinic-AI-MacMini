/**
 * Server-side reads for the order composer.
 *
 * Same tagged-union shape as the other boards: a service picker that renders
 * empty when the backend is unreachable would tell a doctor this clinic offers
 * nothing.
 */

import { getSupabaseServer } from "@/lib/supabase-server";

import type { CatalogueEntry } from "@/app/(dashboard)/doctor/orders/[visitId]/OrderComposer";
import type { WorklistPatient } from "@/lib/worklist";

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
/**
 * Ai là người bệnh của lượt khám này.
 *
 * Trước đây hàm này chỉ trả "Lượt khám đang mở" — một câu về TRẠNG THÁI, không
 * phải một cái tên. Bác sĩ mở màn chỉ định và không thấy mình đang chỉ định
 * siêu âm cho ai; đó là rủi ro nhầm người, không phải lỗi thẩm mỹ.
 *
 * Mọi dòng của một lượt khám cùng một người bệnh, nên đọc dòng đầu là đủ.
 */
export async function fetchVisitPatient(
  visitId: string,
): Promise<WorklistPatient | null> {
  if (!API_BASE) return null;
  const headers = await authHeaders();
  if (!headers) return null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/visits/${visitId}/work-items`, {
      headers,
      cache: "no-store",
    });
    if (!res.ok) return null;
    const rows = (await res.json()) as { patient?: WorklistPatient }[];
    return rows[0]?.patient ?? null;
  } catch {
    return null;
  }
}
