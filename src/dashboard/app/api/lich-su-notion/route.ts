// Lịch sử khám cũ nhập từ Notion (05/10/2026) — chỉ ĐỌC.
//
//   GET ?khach=<clinic_patient_id> → các lượt + lịch hẹn cũ của một khách
//   GET ?luot=<id lượt cũ>         → toàn bộ một lượt (khám, dịch vụ, kết quả, XN, thuốc)
//
// Chỉ là ống dẫn: ai được xem gì do FastAPI quyết (`lich_su_notion_service.py`).

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "@/lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: Request) {
  const q = new URL(request.url).searchParams;
  const khach = q.get("khach");
  const luot = q.get("luot");
  if (khach && UUID_RE.test(khach)) {
    return proxyJsonToBackend("GET", `/api/v1/patients/${khach}/lich-su-notion`, undefined);
  }
  if (luot && UUID_RE.test(luot)) {
    return proxyJsonToBackend("GET", `/api/v1/lich-su-notion/luot/${luot}`, undefined);
  }
  return NextResponse.json(
    { error: "BAD_REQUEST", message: "Thiếu ?khach= hoặc ?luot= hợp lệ." },
    { status: 400 },
  );
}
