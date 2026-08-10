// Việc CSKH tự hẹn: "gọi lại ngày…".
//
//   POST  { clinic_patient_id, ngay_goi, gio_goi?, ly_do }  → tạo việc
//         `gio_goi` bỏ trống = chỉ hẹn tới ngày, KHÔNG phải 00:00.
//   PATCH { id }                                  → đóng việc đã gọi xong
//
// Chỗ đựng những việc hệ thống chưa suy được — gọi hỏi thăm sau thủ thuật,
// chúc mừng đầy tháng sau sinh. Xem 20260809000005 để biết vì sao phải gõ tay.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  return proxyJsonToBackend("POST", "/api/v1/cskh/hen-goi-lai", body);
}

export async function PATCH(request: Request) {
  let body: { id?: string };
  try {
    body = (await request.json()) as { id?: string };
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id việc." }, { status: 400 });
  return proxyJsonToBackend(
    "PATCH",
    `/api/v1/cskh/hen-goi-lai/${encodeURIComponent(id)}`,
    {},
  );
}
