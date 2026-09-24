// Server-side helper to read the clinic's feature mode from Supabase.
// The mode controls which sidebar items are visible (CSKH_ONLY hides clinical screens).

import { cache } from "react";

import { fetchFromBackend } from "./backend-proxy";

export type FeatureMode = "CSKH_ONLY" | "FULL_CLINIC";

const VALID: FeatureMode[] = ["CSKH_ONLY", "FULL_CLINIC"];

/**
 * Read feature_mode from clinic.settings JSONB.
 * Defaults to FULL_CLINIC if not set or invalid.
 */
// cache() = gọi một lần cho cả lượt render. Layout và sidebar cùng hỏi chế độ
// hiển thị; mỗi lần hỏi là một lượt mạng ~180ms sang Seoul.
export const getFeatureMode = cache(async (): Promise<FeatureMode> => {
  // 24/09/2026: đọc qua backend `GET /api/v1/feature-mode` thay vì đọc thẳng
  // `clinic.settings` bằng Supabase. Không đọc được → mặc định FULL_CLINIC.
  const data = await fetchFromBackend<{ mode?: string }>("/api/v1/feature-mode");
  const raw = data?.mode;
  if (typeof raw === "string" && VALID.includes(raw as FeatureMode)) {
    return raw as FeatureMode;
  }
  return "FULL_CLINIC";
});

export function isCskhOnly(mode: FeatureMode): boolean {
  return mode === "CSKH_ONLY";
}

export function isFullClinic(mode: FeatureMode): boolean {
  return mode === "FULL_CLINIC";
}
