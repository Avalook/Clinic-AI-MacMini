// ĐỔI DỊCH VỤ KHÁM TẠI CHỖ (V5, Tuyền chốt 30/09/2026) — proxy mỏng.
//
//   GET  ?id=<lịch>            → danh sách loại khám + đổi được không, vì sao
//        (máy chủ quyết: services/doi_dich_vu_kham.py).
//   POST { id, service_type_id } → đổi loại khám của lịch (và của lượt khám nếu
//        đã check-in mà chưa vướng gì) — BookingService.doi_dich_vu_kham.
//   Quyền do máy chủ hỏi ("Quản lý lịch hẹn" hoặc "Check-in khách").

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: Request) {
  const id = (new URL(request.url).searchParams.get("id") ?? "").trim();
  if (!UUID_RE.test(id)) {
    return NextResponse.json({ error: "Thiếu mã lịch hẹn." }, { status: 400 });
  }
  return proxyJsonToBackend("GET", `/api/v1/appointments/${id}/doi-dich-vu-kham`, null);
}

interface Body {
  id?: string;
  service_type_id?: string;
}

export async function POST(request: Request) {
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!UUID_RE.test(id)) {
    return NextResponse.json({ error: "Thiếu mã lịch hẹn." }, { status: 400 });
  }
  const dv = (body.service_type_id ?? "").trim();
  if (!UUID_RE.test(dv)) {
    return NextResponse.json({ error: "Chọn dịch vụ khám." }, { status: 400 });
  }
  return proxyJsonToBackend("POST", `/api/v1/appointments/${id}/doi-dich-vu-kham`, {
    service_type_id: dv,
  });
}
