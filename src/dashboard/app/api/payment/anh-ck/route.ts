// /api/payment/anh-ck — ẢNH CHUYỂN KHOẢN của một lần thu (01/10/2026). Chỉ
// chuyển tiếp; quyền, kiểu ảnh, nơi lưu đều ở FastAPI (`anh_chuyen_khoan_service`).
//   POST   multipart (file, payment_cycle_id)  → lưu ảnh (ổ VPS → CFS)
//   GET    ?id=<anh>                           → nội dung ảnh (không cache)
//   DELETE ?id=<anh>                           → gỡ ảnh nhầm (ẩn, giữ vết)

import { NextResponse } from "next/server";

import { chuyenTiepTaiLen } from "@/lib/chuyen-tiep-tai-len";
import { getCallerAuthHeaders, proxyJsonToBackend } from "../../../../lib/backend-proxy";

const API_BASE = process.env.CLINIC_API_URL;

function maAnh(request: Request): string {
  return (new URL(request.url).searchParams.get("id") ?? "").trim();
}

export async function GET(request: Request) {
  if (!API_BASE) {
    return NextResponse.json({ error: "CLINIC_API_URL chưa được cấu hình." }, { status: 503 });
  }
  const auth = await getCallerAuthHeaders();
  if (!auth) return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  const id = maAnh(request);
  if (!id) return NextResponse.json({ error: "Thiếu mã ảnh." }, { status: 400 });
  let res: Response;
  try {
    res = await fetch(
      `${API_BASE}/api/v1/payments/anh-chuyen-khoan/${encodeURIComponent(id)}`,
      { headers: auth, cache: "no-store" },
    );
  } catch {
    return NextResponse.json({ error: "Không kết nối được máy chủ xử lý" }, { status: 502 });
  }
  const ra: Record<string, string> = {
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "private, no-store",
  };
  for (const h of ["content-type", "content-length"]) {
    const v = res.headers.get(h);
    if (v) ra[h] = v;
  }
  return new Response(res.body, { status: res.status, headers: ra });
}

export async function POST(request: Request) {
  if (!API_BASE) {
    return NextResponse.json({ error: "CLINIC_API_URL chưa được cấu hình." }, { status: 503 });
  }
  const headers = await getCallerAuthHeaders();
  if (!headers) return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  // Chuyển tiếp NGUYÊN VĂN multipart — kèm Content-Type (boundary), xem
  // cskh/ket-qua/route.ts: thiếu nó FastAPI không đọc được thân.
  const ctIn = request.headers.get("content-type");
  if (ctIn) headers["Content-Type"] = ctIn;
  const clIn = request.headers.get("content-length");
  if (clIn) headers["Content-Length"] = clIn;
  let res: { status: number; text: string };
  try {
    res = await chuyenTiepTaiLen(
      `${API_BASE}/api/v1/payments/anh-chuyen-khoan`,
      request,
      headers,
    );
  } catch {
    return NextResponse.json(
      { error: "Mất kết nối giữa chừng — ảnh CHƯA được lưu, hãy tải lại." },
      { status: 502 },
    );
  }
  let payload: unknown = {};
  try {
    payload = res.text ? JSON.parse(res.text) : {};
  } catch {
    payload = { error: res.text || "Lỗi máy chủ" };
  }
  return NextResponse.json(payload, { status: res.status });
}

export async function DELETE(request: Request) {
  const id = maAnh(request);
  if (!id) return NextResponse.json({ error: "Thiếu mã ảnh." }, { status: 400 });
  return proxyJsonToBackend(
    "POST",
    `/api/v1/payments/anh-chuyen-khoan/${encodeURIComponent(id)}/go`,
    {},
  );
}
