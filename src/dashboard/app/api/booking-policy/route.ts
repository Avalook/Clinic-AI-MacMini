// Proxy for the clinic's booking policy (slot length + seat counts, C.3).
//
// GET  → who reads the policy already goes through the layout
//        (lib/booking-policy.ts → backend /api/v1/appointments/policy).
// PATCH → Trưởng ca + Quản lý change THEIR clinic's numbers; the backend
//        derives the clinic from the caller's membership, not from the body,
//        so this route never needs to know which clinic is being edited.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole } from "../../../lib/clinic-session";
import { isOpsAdmin } from "../../../lib/roles";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";

export async function PATCH(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const role = await getClinicRole();
  if (!isOpsAdmin(role)) {
    return NextResponse.json({ error: "Chỉ Trưởng ca / Quản lý mới được sửa luật đặt lịch." }, { status: 403 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  return proxyJsonToBackend("PATCH", "/api/v1/booking-policy", body);
}