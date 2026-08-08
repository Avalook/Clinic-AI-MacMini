// Phản hồi / khiếu nại của khách (DoD CSKH mục 3).
//
//   POST  { clinic_patient_id, loai, noi_dung }        → ghi một phản hồi
//   PATCH { id, trang_thai, huong_xu_ly? }             → chuyển trạng thái xử lý
//
// Đi qua FastAPI (ADR-0012): người tiếp nhận và người xử lý lấy từ phiên đăng
// nhập, không nhận từ trình duyệt.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  return proxyJsonToBackend("POST", "/api/v1/cskh/phan-hoi", body);
}

export async function PATCH(request: Request) {
  let body: { id?: string; trang_thai?: string; huong_xu_ly?: string };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!id) {
    return NextResponse.json({ error: "Thiếu id phản hồi." }, { status: 400 });
  }
  return proxyJsonToBackend(
    "PATCH",
    `/api/v1/cskh/phan-hoi/${encodeURIComponent(id)}`,
    { trang_thai: body.trang_thai, huong_xu_ly: body.huong_xu_ly ?? null },
  );
}
