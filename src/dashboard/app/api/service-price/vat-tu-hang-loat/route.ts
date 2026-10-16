// Đặt cờ vật tư HÀNG LOẠT theo loại (Kho vật tư → Danh mục) — chỉ chuyển tiếp.
//   POST { loai, co, bat, ap_dung?, ids? } → POST /api/v1/service-prices/vat-tu/hang-loat
//
// `ap_dung` vắng/false = chỉ ĐẾM ("sẽ đổi N vật tư"), true = ghi. Quyền
// (`price.service.manage`, cùng quyền sửa thuộc tính từng món) và mọi luật — loại lạ,
// cờ lạ, chỉ đổi hàng đang bán, dấu vết — do MÁY CHỦ quyết; ở đây chỉ kiểm đăng nhập,
// JSON hợp lệ và chỉ chuyển đúng bốn khoá (rác đi nguyên văn để máy chủ trả 422 có câu).

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";
import { getSupabaseServer } from "../../../../lib/supabase-server";

export async function POST(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  let body: Record<string, unknown>;
  try {
    const goc: unknown = await request.json();
    if (goc === null || typeof goc !== "object" || Array.isArray(goc)) throw new Error("hinh");
    body = goc as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  return proxyJsonToBackend("POST", "/api/v1/service-prices/vat-tu/hang-loat", {
    loai: body.loai,
    co: body.co,
    bat: body.bat,
    ap_dung: body.ap_dung ?? false,
    ...("ids" in body ? { ids: body.ids } : {}),
  });
}
