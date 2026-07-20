// Browser-side Supabase client (client components, hooks).
// Uses ANON key (public, RLS-gated). Do NOT introduce service_role here.

import { createBrowserClient } from "@supabase/ssr";

export function getSupabaseBrowser() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
