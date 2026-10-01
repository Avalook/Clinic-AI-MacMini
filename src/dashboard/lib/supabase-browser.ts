// Browser-side Supabase client (client components, hooks).
// Uses ANON key (public, RLS-gated). Do NOT introduce service_role here.
// URL + khoá anon đọc LÚC CHẠY (lib/cau-hinh-cong-khai.ts) — không nung vào ảnh.

import { createBrowserClient } from "@supabase/ssr";
import { cauHinhCongKhai } from "./cau-hinh-cong-khai";
import { tenCookieSupabase } from "./supabase-cookie";

export function getSupabaseBrowser() {
  const c = cauHinhCongKhai();
  return createBrowserClient(c.supabaseUrl, c.supabaseAnonKey, {
    cookieOptions: { name: tenCookieSupabase() },
  });
}
