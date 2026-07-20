// Service-role Supabase client — SERVER ONLY (route handlers / server actions).
// Bypasses RLS, so it is used for the data-entry WRITE path (RLS on patient /
// appointment only has SELECT policies → authenticated INSERTs are denied).
// NEVER import this from a client component.

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/** Returns a service-role client, or null if the key is not configured. */
export function getSupabaseService(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return null;
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
