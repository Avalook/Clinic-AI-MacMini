// /api/catalog/dich-vu-dat-lich — ô chọn dịch vụ khi đặt / sửa lịch (4 nhóm:
// Khám · Điều trị · Thuốc ẩn · Khác). Nhóm do backend gom
// (`services/dich_vu_dat_lich.py`), route chỉ chuyển tiếp (SO-LUAT Phần 3).

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";
import { getSupabaseServer } from "../../../../lib/supabase-server";

export async function GET() {
  const db = await getSupabaseServer();
  const {
    data: { user },
  } = await db.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  return proxyJsonToBackend("GET", "/api/v1/catalog/dich-vu-dat-lich", undefined);
}
