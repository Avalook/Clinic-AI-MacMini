// Client-safe constants for feature mode filtering.
// This file has NO server imports (no next/headers, no supabase-server),
// so it is safe to import from "use client" components like Nav.tsx.

/** Nav hrefs to HIDE when in CSKH_ONLY mode (clinical workflow screens). */
export const CLINICAL_HREFS = new Set([
  "/reception/queue",
  "/do-sinh-hieu",
  "/ban-kham",
  "/ban-kham/KN-NOITIET",
  "/ban-kham/KN-SANCHAU",
  "/ban-kham/KN-SAN-BIO",
  "/phong/KN-LAYMAU",
  "/phong/KN-SA-T1",
  "/phong/KN-SA1",
  "/phong/KN-SA2",
  "/phong/KN-THUTHUAT",
  "/phong/KN-TTNG",
  "/phong/KN-SANCHAU",
  "/phong/KN-SAN-BIO",
  "/duyet-ket-qua",
  "/cashier/board",
  "/pharmacy",
  "/pharmacy/inventory",
  "/pharmacy/history",
  "/pharmacy/consult",
  "/queue",
]);
