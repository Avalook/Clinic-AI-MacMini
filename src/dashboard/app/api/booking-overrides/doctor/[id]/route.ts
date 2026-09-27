// Proxy for deleting doctor booking override (C.4)

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../../lib/supabase-server";
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

  // Cửa quyền là việc của BACKEND (config.clinic.manage — lego Cài đặt) — proxy chỉ kiểm đã đăng nhập
  // (kiểm toán 27/09/2026: cửa vai ở đây chặn người đã được cấp lego).

  const { id } = await params;
  return proxyJsonToBackend(
    "DELETE",
    `/api/v1/booking-overrides/doctor/${id}`,
    {},
  );
}
