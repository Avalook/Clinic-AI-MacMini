// ĐỔI LỊCH TẠI CHỖ (Tuyền chốt 29/09/2026) — proxy mỏng.
//
//   GET  ?id=<lịch>&ngay=YYYY-MM-DD → ô giờ của popover Đổi lịch (máy chủ quyết
//        trạng thái ô: services/doi_lich_nhanh.py).
//   POST { id, slot_start, slot_end, doctor_id, ly_do, check_in, idempotency_key }
//        → đổi lịch (+ check-in luôn) trong MỘT giao dịch
//        (BookingService.doi_lich_nhanh). Quyền do máy chủ hỏi.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const NGAY_RE = /^\d{4}-\d{2}-\d{2}$/;

export async function GET(request: Request) {
  const sp = new URL(request.url).searchParams;
  const id = (sp.get("id") ?? "").trim();
  if (!UUID_RE.test(id)) {
    return NextResponse.json({ error: "Thiếu mã lịch hẹn." }, { status: 400 });
  }
  const ngay = (sp.get("ngay") ?? "").trim();
  const q = NGAY_RE.test(ngay) ? `?ngay=${ngay}` : "";
  return proxyJsonToBackend("GET", `/api/v1/appointments/${id}/doi-lich-nhanh${q}`, null);
}

interface Body {
  id?: string;
  slot_start?: string;
  slot_end?: string;
  doctor_id?: string;
  ly_do?: string;
  check_in?: boolean;
  idempotency_key?: string;
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
  const khoa = (body.idempotency_key ?? "").trim().slice(0, 200) || undefined;
  return proxyJsonToBackend(
    "POST",
    `/api/v1/appointments/${id}/doi-lich-nhanh`,
    {
      slot_start: body.slot_start ?? null,
      slot_end: body.slot_end ?? null,
      doctor_id: body.doctor_id ?? null,
      ly_do: body.ly_do ?? "",
      check_in: body.check_in === true,
    },
    khoa,
  );
}
