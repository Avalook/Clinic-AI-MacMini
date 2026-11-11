// /api/xet-nghiem/kho-email-pdf?id=<drive_tep> — PDF kết quả đối tác về Gmail, xem ở
// Kho email (Gmail G2b, 09/11/2026). Chỉ chuyển tiếp: máy chủ kiểm quyền
// `xet_nghiem.kho_email` (thiếu ⇒ 404), đọc tệp đã lưu (ổ VPS / CFS) và ghi vết
// `lab.archive_viewed` mỗi lần mở. Trình duyệt không bao giờ gọi Gmail.
//   GET ?id=<uuid> → `/api/v1/xet-nghiem/kho-email/{id}/pdf` (không lưu đệm)

import { NextResponse } from "next/server";

import { getCallerAuthHeaders } from "../../../../lib/backend-proxy";

const API_BASE = process.env.CLINIC_API_URL;
const U = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: Request) {
  if (!API_BASE) return NextResponse.json({ error: "CLINIC_API_URL chưa được cấu hình." }, { status: 503 });
  const auth = await getCallerAuthHeaders();
  if (!auth) return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  const id = (new URL(request.url).searchParams.get("id") ?? "").trim();
  if (!U.test(id)) return NextResponse.json({ error: "Mã thư không hợp lệ." }, { status: 400 });
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1/xet-nghiem/kho-email/${id}/pdf`, { headers: auth, cache: "no-store" });
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
