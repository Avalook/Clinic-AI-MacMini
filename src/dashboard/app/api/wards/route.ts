// /api/wards?province=<code> → danh sách phường/xã của 1 tỉnh (sau sáp nhập, bỏ
// huyện). Data tham chiếu hành chính TĨNH, CÔNG KHAI (không nhạy cảm). Đọc bằng
// SERVICE-ROLE: bảng province/ward có RLS bật nhưng KHÔNG có policy SELECT → client
// authenticated đọc ra 0 dòng. Bypass RLS ở server cho data tham chiếu là an toàn.

import { NextResponse } from "next/server";
import { getSupabaseService } from "../../../lib/supabase-service";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const province = new URL(request.url).searchParams.get("province")?.trim();
  if (!province) {
    return NextResponse.json({ wards: [] });
  }
  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }
  const { data, error } = await db
    .from("ward")
    .select("code, name, full_name")
    .eq("province_code", province)
    .order("name");
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  return NextResponse.json({ wards: data ?? [] });
}
