// Proxy for doctor booking overrides (C.4)

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getClinicRole } from "../../../../lib/clinic-session";
import { isOpsAdmin } from "../../../../lib/roles";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

// Không có GET ở đây. Bản cũ có một handler GET gọi POST tới
// `/api/v1/booking-overrides/doctor/list` — một đường dẫn không tồn tại ở
// backend, nên nó luôn trả 404 và không màn nào gọi nó. Trang cấu hình đọc danh
// sách luật thẳng từ server component (lib/booking-policy.ts → listStandingRules),
// nên route này chỉ còn việc GHI.

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

  return proxyJsonToBackend("POST", "/api/v1/booking-overrides/doctor", body);
}
