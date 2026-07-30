// /api/wards?province=<code> → danh sách phường/xã của 1 tỉnh (sau sáp nhập, bỏ
// huyện). Data tham chiếu hành chính TĨNH, CÔNG KHAI (không nhạy cảm).
//
// Đọc bằng session của chính người gọi. Trước đây route này phải dùng
// SERVICE-ROLE vì `ward` bật RLS mà không có policy SELECT nào (client
// authenticated đọc ra 0 dòng); migration 20260730000002 đã thêm policy cho
// province/ward nên không cần bypass RLS nữa — xem ADR-0012.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const province = new URL(request.url).searchParams.get("province")?.trim();
  if (!province) {
    return NextResponse.json({ wards: [] });
  }
  const db = await getSupabaseServer();
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
