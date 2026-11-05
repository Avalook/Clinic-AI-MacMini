// /api/xet-nghiem/drive-tep?id=<drive_tep> — xem trước tệp Drive CHƯA ghép (chặng 4,
// 05/11/2026). Chỉ chuyển tiếp: máy chủ đọc Drive bằng tài khoản dịch vụ chỉ đọc
// (`services/xet_nghiem/ghep_tay.noi_dung_cho`); trình duyệt không bao giờ gọi Drive.
//   GET ?id=<uuid> → `/api/v1/xet-nghiem/ban/drive-tep/{id}` (không lưu đệm)

import { NextResponse } from "next/server";

import { getCallerAuthHeaders } from "../../../../lib/backend-proxy";

const API_BASE = process.env.CLINIC_API_URL;
const U = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: Request) {
  if (!API_BASE) return NextResponse.json({ error: "CLINIC_API_URL chưa được cấu hình." }, { status: 503 });
  const auth = await getCallerAuthHeaders();
  if (!auth) return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  const id = (new URL(request.url).searchParams.get("id") ?? "").trim();
  if (!U.test(id)) return NextResponse.json({ error: "Mã tệp không hợp lệ." }, { status: 400 });
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1/xet-nghiem/ban/drive-tep/${id}`, { headers: auth, cache: "no-store" });
  } catch {
    return NextResponse.json({ error: "Không kết nối được máy chủ xử lý" }, { status: 502 });
  }
  const ra: Record<string, string> = { "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store" };
  for (const h of ["content-type", "content-length"]) {
    const v = res.headers.get(h);
    if (v) ra[h] = v;
  }
  return new Response(res.body, { status: res.status, headers: ra });
}
