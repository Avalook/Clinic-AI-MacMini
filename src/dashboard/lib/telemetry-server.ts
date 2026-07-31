/**
 * Reading API telemetry. SERVER ONLY.
 *
 * Same tagged-union shape as the worklist for the same reason: a monitoring
 * screen that renders zeros when it cannot reach the backend is worse than one
 * that says so, because zeros look like health.
 */

import { getSupabaseServer } from "@/lib/supabase-server";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

export interface RouteTiming {
  method: string;
  route: string;
  count: number;
  p50_ms: number;
  p95_ms: number;
  max_ms: number;
}

export interface ApiError {
  route: string;
  method: string;
  status: number;
  at: number;
  request_id: string | null;
  kind: string;
  detail: string;
}

export interface TelemetrySnapshot {
  since: number;
  window_s: number | null;
  total: number;
  statuses: Record<string, number>;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  slow_count: number;
  slow_threshold_ms: number;
  routes: RouteTiming[];
  errors: ApiError[];
}

export type TelemetryResult =
  | { ok: true; data: TelemetrySnapshot }
  | { ok: false; reason: "no-session" | "unreachable" | "refused" | "forbidden"; detail?: string };

export async function fetchTelemetry(windowSeconds = 900): Promise<TelemetryResult> {
  if (!API_BASE) {
    return { ok: false, reason: "unreachable", detail: "CLINIC_API_URL chưa cấu hình" };
  }

  const supabase = await getSupabaseServer();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) return { ok: false, reason: "no-session" };

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  try {
    const res = await fetch(
      `${API_BASE}/api/v1/ops/telemetry?window_s=${windowSeconds}`,
      { headers, cache: "no-store" },
    );
    // 403 is its own case: the screen should explain the role requirement
    // rather than look broken to someone who simply may not see this.
    if (res.status === 403) return { ok: false, reason: "forbidden" };
    if (!res.ok) return { ok: false, reason: "refused", detail: `HTTP ${res.status}` };
    return { ok: true, data: (await res.json()) as TelemetrySnapshot };
  } catch (e) {
    return {
      ok: false,
      reason: "unreachable",
      detail: e instanceof Error ? e.message : undefined,
    };
  }
}
