// Đường ĐỌC cho bảng điều phối, dùng bởi nhịp làm mới 3 giây phía trình duyệt.
//
// Tách khỏi `/api/dispatch/[action]` (đường GHI) vì hai thứ có quyền khác nhau:
// đọc mở cho vai vận hành, ghi chỉ Trưởng ca/Quản lý. Gộp chung một handler thì
// một lần sửa nhầm điều kiện là mở luôn quyền ghi.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { fetchFromBackend } from "../../../lib/backend-proxy";

const READS: Record<string, string> = {
  overview: "/api/v1/dispatch/overview",
  alerts: "/api/v1/dispatch/alerts",
  history: "/api/v1/dispatch/history?limit=200",
  routes: "/api/v1/dispatch/routes",
};

export async function GET(request: Request) {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const what = new URL(request.url).searchParams.get("what") ?? "overview";
  const path = READS[what];
  if (!path) {
    return NextResponse.json({ error: `Không có "${what}"` }, { status: 400 });
  }

  const data = await fetchFromBackend<Record<string, unknown>>(path);
  // `null` = backend không trả lời. Trả `ok: false` để màn hình bật chỉ báo
  // "dữ liệu cũ X giây" thay vì âm thầm giữ số cũ như thể vẫn đang cập nhật.
  return NextResponse.json(data ?? { ok: false });
}
