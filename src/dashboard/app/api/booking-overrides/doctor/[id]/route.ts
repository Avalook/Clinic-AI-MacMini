// Proxy for deleting doctor booking override (C.4)

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../../lib/supabase-server";
import { getClinicRole } from "../../../../../lib/clinic-session";
import { isOpsAdmin } from "../../../../../lib/roles";
import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const role = await getClinicRole();
  if (!isOpsAdmin(role)) {
    return NextResponse.json(
      { error: "Chỉ Trưởng ca / Quản lý mới được sửa luật đặt lịch." },
      { status: 403 },
    );
  }

  const { id } = await params;
  return proxyJsonToBackend(
    "DELETE",
    `/api/v1/booking-overrides/doctor/${id}`,
    {},
  );
}
