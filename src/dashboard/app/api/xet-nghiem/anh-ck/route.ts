// /api/xet-nghiem/anh-ck — ẢNH CHUYỂN KHOẢN của một khoản THU HỘ đối tác (05/11/2026,
// kế hoạch 4.4 phương án b). Chỉ chuyển tiếp; quyền, kiểu ảnh, nơi lưu ở FastAPI
// (`services/xet_nghiem/anh_ck.py`). Gỡ ảnh đi qua `[...duong]` (`ban/anh-ck/{id}/go`).
//   POST multipart (file, thanh_toan_id) → `/api/v1/xet-nghiem/ban/anh-ck`
//   GET  ?id=<anh>                        → `/api/v1/xet-nghiem/ban/anh-ck/{id}` (không cache)

import { NextResponse } from "next/server";

import { chuyenTiepTaiLen } from "@/lib/chuyen-tiep-tai-len";

import { getCallerAuthHeaders } from "../../../../lib/backend-proxy";

const API_BASE = process.env.CLINIC_API_URL;
const U = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: Request) {
  if (!API_BASE) return NextResponse.json({ error: "CLINIC_API_URL chưa được cấu hình." }, { status: 503 });
  const auth = await getCallerAuthHeaders();
  if (!auth) return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  const id = (new URL(request.url).searchParams.get("id") ?? "").trim();
  if (!U.test(id)) return NextResponse.json({ error: "Mã ảnh không hợp lệ." }, { status: 400 });
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1/xet-nghiem/ban/anh-ck/${id}`, { headers: auth, cache: "no-store" });
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

export async function POST(request: Request) {
  if (!API_BASE) return NextResponse.json({ error: "CLINIC_API_URL chưa được cấu hình." }, { status: 503 });
  const headers = await getCallerAuthHeaders();
  if (!headers) return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  // PHẢI chuyển Content-Type (boundary) — thiếu thì FastAPI không đọc được thân.
  const ct = request.headers.get("content-type");
  if (ct) headers["Content-Type"] = ct;
  const cl = request.headers.get("content-length");
  if (cl) headers["Content-Length"] = cl;
  let res: { status: number; text: string };
  try {
    res = await chuyenTiepTaiLen(`${API_BASE}/api/v1/xet-nghiem/ban/anh-ck`, request, headers);
  } catch {
    return NextResponse.json({ error: "Mất kết nối giữa chừng — ảnh CHƯA được lưu." }, { status: 502 });
  }
  let payload: unknown = {};
  try {
    payload = res.text ? JSON.parse(res.text) : {};
  } catch {
    payload = { error: res.text || "Lỗi máy chủ" };
  }
  return NextResponse.json(payload, { status: res.status });
}
