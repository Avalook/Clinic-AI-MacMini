// Client-safe constants for feature mode filtering.
// This file has NO server imports (no next/headers, no supabase-server),
// so it is safe to import from "use client" components like Nav.tsx.

/** Nav hrefs to HIDE when in CSKH_ONLY mode (clinical workflow screens). */
export const CLINICAL_HREFS = new Set([
  "/reception/queue",
  "/do-sinh-hieu",
  "/ban-kham",
  "/tu-van",
  // Mọi màn theo phòng (`/phong/<room_id>`, `/ban-kham/<room_id>`) cũng là màn
  // lâm sàng — `laManLamSang` ở nav-items.ts khớp theo tiền tố (CORE-C).
  "/phong",
  "/duyet-ket-qua",
  // /cashier/board gộp vào hai quầy dưới đây 18/09/2026 (docs/SITEMAP.md).
  "/thu-ngan/dich-vu",
  "/thu-ngan/thuoc",
  "/pharmacy",
  "/pharmacy/inventory",
  "/pharmacy/history",
  "/pharmacy/consult",
]);
