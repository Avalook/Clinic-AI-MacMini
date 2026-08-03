// Client-safe constants for feature mode filtering.
// This file has NO server imports (no next/headers, no supabase-server),
// so it is safe to import from "use client" components like Nav.tsx.

/** Nav hrefs to HIDE when in CSKH_ONLY mode (clinical workflow screens). */
export const CLINICAL_HREFS = new Set([
  "/reception/queue",
  "/doctor/board",
  "/cashier/board",
  "/sono",
  "/lab-queue",
  "/service-queue",
  "/pharmacy",
  "/pharmacy/inventory",
  "/pharmacy/history",
  "/pharmacy/consult",
  "/result-review",
  "/queue",
]);
