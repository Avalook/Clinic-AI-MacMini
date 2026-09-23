// /api/catalog — danh mục cho ô kê của bệnh án (thuốc kho + dịch vụ CLS).
//
// 24/09/2026: đi qua backend `GET /api/v1/catalog/danh-muc-ke` (lọc đúng phòng
// khám người gọi) thay vì đọc thẳng `drug_catalog` / `service_price` bằng
// Supabase — frontend chỉ là giao diện (SO-LUAT Phần 3).

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";
import { getSupabaseServer } from "../../../lib/supabase-server";

export async function GET() {
  const db = await getSupabaseServer();
  const {
    data: { user },
  } = await db.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  return proxyJsonToBackend("GET", "/api/v1/catalog/danh-muc-ke", undefined);
}
