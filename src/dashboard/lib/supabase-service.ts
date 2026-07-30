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

/** The env var's name, for operator-facing messages.
 *
 * Exported so a page can tell the operator which variable to set without
 * writing the name itself — the ADR-0012 boundary test counts any file that
 * mentions it, and a warning banner is not a file that touches the key.
 */
export const SERVICE_ROLE_ENV = "SUPABASE_SERVICE_ROLE_KEY";

/** Whether the server has a service-role key at all.
 *
 * The new-user page shows a warning before the operator fills the form, because
 * the Supabase Auth admin API is the one thing that still needs this key. The
 * page asks here rather than reading the variable itself: the ADR-0012
 * allowlist should name the modules that can touch the key, and a page that
 * only wants a yes/no is not one of them.
 */
export function hasServiceRoleKey(): boolean {
  return Boolean(process.env.SUPABASE_SERVICE_ROLE_KEY);
}
