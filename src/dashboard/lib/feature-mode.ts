// Server-side helper to read the clinic's feature mode from Supabase.
// The mode controls which sidebar items are visible (CSKH_ONLY hides clinical screens).

import { cache } from "react";

import { getSupabaseServer } from "./supabase-server";

export type FeatureMode = "CSKH_ONLY" | "FULL_CLINIC";

const VALID: FeatureMode[] = ["CSKH_ONLY", "FULL_CLINIC"];

/**
 * Read feature_mode from clinic.settings JSONB.
 * Defaults to FULL_CLINIC if not set or invalid.
 */
// cache() = gọi một lần cho cả lượt render. Layout và sidebar cùng hỏi chế độ
// hiển thị; mỗi lần hỏi là một lượt mạng ~180ms sang Seoul.
export const getFeatureMode = cache(async (): Promise<FeatureMode> => {
  try {
    const supabase = await getSupabaseServer();
    const { data } = await supabase
      .from("clinic")
      .select("settings")
      .limit(1)
      .maybeSingle();
    const raw = (data?.settings as Record<string, unknown>)?.feature_mode;
    if (typeof raw === "string" && VALID.includes(raw as FeatureMode)) {
      return raw as FeatureMode;
    }
  } catch {
    // Graceful fallback — DB may not have clinic table yet.
  }
  return "FULL_CLINIC";
});

export function isCskhOnly(mode: FeatureMode): boolean {
  return mode === "CSKH_ONLY";
}

export function isFullClinic(mode: FeatureMode): boolean {
  return mode === "FULL_CLINIC";
}
