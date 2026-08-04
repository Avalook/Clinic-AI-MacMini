// Đóng lượt khám — proxy xuống FastAPI.
//
// Đóng lượt KHÔNG đụng `visit.status`: đó là khoá hồ sơ bệnh án theo
// TT13/2011/TT-BYT. Toàn bộ luật nằm ở checkout_service.py; route này chỉ
// chuyển tiếp và gác quyền.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getClinicRole } from "../../../../lib/clinic-session";
import { proxyJsonToBackend, fetchFromBackend } from "../../../../lib/backend-proxy";

const ALLOWED = ["RECEPTION", "TRUONG_CA", "MANAGEMENT"];

async function guard() {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return "Chưa đăng nhập";
  const role = await getClinicRole();
  if (!role || !ALLOWED.includes(role)) {
    return "Chỉ Lễ tân / Trưởng ca / Quản lý mới đóng được lượt khám.";
  }
  return null;
}

export async function GET(request: Request) {
  const err = await guard();
  if (err) return NextResponse.json({ error: err }, { status: 403 });

  // Một lượt cụ thể, hay cả danh sách hôm nay.
  const visit = new URL(request.url).searchParams.get("visit_id");
  const data = await fetchFromBackend<unknown>(
    visit
      ? `/api/v1/reception/checkout/${encodeURIComponent(visit)}`
      : "/api/v1/reception/checkout",
  );
  // `null` = backend im lặng. Trả ok:false để màn hình nói ra, thay vì vẽ một
  // danh sách rỗng trông y hệt "hôm nay không còn ai cần đóng".
  return NextResponse.json(data ?? { ok: false });
}

export async function POST(request: Request) {
  const err = await guard();
  if (err) return NextResponse.json({ error: err }, { status: 403 });

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  return proxyJsonToBackend("POST", "/api/v1/reception/checkout", body);
}
