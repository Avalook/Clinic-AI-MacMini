// Ghi một luật số chỗ. Một đường cho cả luật mãi mãi lẫn luật có ngày —
// backend chọn bảng theo việc có khoảng ngày hay không, nên trình duyệt không
// phải biết hệ thống có mấy tầng.
//
// Không có GET ở đây: trang cấu hình đọc danh sách thẳng từ server component
// (lib/booking-policy.ts → listBookingRules).

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole } from "../../../lib/clinic-session";
import { isOpsAdmin } from "../../../lib/roles";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";

export async function POST(request: Request) {
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

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  return proxyJsonToBackend("POST", "/api/v1/booking-rules", body);
}
