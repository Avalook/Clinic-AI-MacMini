/**
 * Reading a workspace's queue from the backend. SERVER ONLY.
 *
 * Kept apart from lib/worklist.ts because the queue board is a client
 * component: when the fetch and the types lived in one module, importing the
 * type dragged supabase-server — and cookies() — into the browser bundle and
 * the page 500'd. Types and pure helpers go in worklist.ts, anything touching a
 * session goes here.
 *
 * This deliberately does NOT use fetchFromBackend. That helper returns null on
 * any failure because its callers show progress indicators, and a missing
 * indicator beats a broken page. Here the queue IS the page: if the backend is
 * down and we render an empty list, the front desk sees "nobody is waiting"
 * while eighteen people sit in the waiting room. An outage and an empty queue
 * must not look the same, so the result is a tagged union and the screen is
 * forced to handle both.
 */

import { getSupabaseServer } from "@/lib/supabase-server";

import type { WorklistItem } from "@/lib/worklist";

// CLINIC_API_URL is the convention the rest of the dashboard already uses
// (lib/backend-proxy.ts). Inventing a second variable meant reads and writes
// pointed at different places: the board loaded while every command 503'd.
const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

export type WorklistResult =
  | { ok: true; items: WorklistItem[] }
  | { ok: false; reason: "no-session" | "unreachable" | "refused"; detail?: string };

export async function fetchWorklist(
  workspace: string,
  opts: { date?: string; mineOnly?: boolean } = {},
): Promise<WorklistResult> {
  if (!API_BASE) return { ok: false, reason: "unreachable", detail: "CLINIC_API_URL chưa cấu hình" };

  const supabase = await getSupabaseServer();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) return { ok: false, reason: "no-session" };

  const params = new URLSearchParams({ workspace });
  if (opts.date) params.set("date", opts.date);
  if (opts.mineOnly) params.set("mine_only", "true");

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  try {
    const res = await fetch(`${API_BASE}/api/v1/work-items?${params}`, {
      headers,
      cache: "no-store",
    });
    if (!res.ok) {
      return { ok: false, reason: "refused", detail: `HTTP ${res.status}` };
    }
    return { ok: true, items: (await res.json()) as WorklistItem[] };
  } catch (e) {
    return {
      ok: false,
      reason: "unreachable",
      detail: e instanceof Error ? e.message : undefined,
    };
  }
}
