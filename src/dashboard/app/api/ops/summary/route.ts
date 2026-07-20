import { NextResponse } from "next/server";

import { getClinicRole } from "../../../../lib/clinic-session";
import { buildOpsLinks, emptyOpsSummary, normalizeOpsPayload } from "../../../../lib/ops-summary";
import { isAdminRole } from "../../../../lib/roles";
import { getSupabaseServer } from "../../../../lib/supabase-server";

export const dynamic = "force-dynamic";

function json(body: unknown, status = 200) {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "private, no-store" },
  });
}

export async function GET() {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return json({ error: "Unauthorised" }, 401);

  const role = await getClinicRole();
  if (!isAdminRole(role)) return json({ error: "Forbidden" }, 403);

  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  const apiBase = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");
  const apiKey = process.env.BACKEND_API_KEY;
  const links = buildOpsLinks(process.env);
  if (!token || !apiBase || !apiKey) {
    return json({ ...emptyOpsSummary(), links, sourceUnavailable: true });
  }

  try {
    const response = await fetch(`${apiBase}/api/v1/ops/status`, {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        "X-API-Key": apiKey,
      },
      cache: "no-store",
      signal: AbortSignal.timeout(4_000),
    });
    if (!response.ok) {
      return json({ ...emptyOpsSummary(), links, sourceUnavailable: true });
    }
    const summary = normalizeOpsPayload(await response.json());
    return json({ ...summary, links, sourceUnavailable: false });
  } catch {
    return json({ ...emptyOpsSummary(), links, sourceUnavailable: true });
  }
}

