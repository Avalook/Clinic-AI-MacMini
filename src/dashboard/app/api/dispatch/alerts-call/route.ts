// Trưởng ca gọi một bộ phận.
//
// Đường RIÊNG, không nhét vào `/api/dispatch/[action]`: danh sách trắng ở đó
// chỉ dành cho bốn thao tác ĐIỀU PHỐI (chuyển bước, đổi phòng, áp tuyến, đổi
// ngưỡng). Gọi người là việc khác — nó tạo ra thứ hiện lên màn hình của người
// khác — nên nó có cửa riêng và gác riêng.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getClinicRole } from "../../../../lib/clinic-session";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function POST(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const role = await getClinicRole();
  if (role !== "TRUONG_CA" && role !== "MANAGEMENT") {
    return NextResponse.json(
      { error: "Chỉ Trưởng ca / Quản lý mới gọi được bộ phận." },
      { status: 403 },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  return proxyJsonToBackend("POST", "/api/v1/dispatch/alerts/call", body);
}
