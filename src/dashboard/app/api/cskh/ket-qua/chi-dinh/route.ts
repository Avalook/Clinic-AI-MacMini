// Chỉ định của lượt khám (theo lịch hẹn) — ô "Kết quả của chỉ định nào" khi tải
// tệp ở màn Khách hàng (27/09/2026, đợt 3).
//
//   GET ?appointment_id=…  → FastAPI GET /api/v1/cskh/ket-qua/chi-dinh-cua-lich/{id}
//
// Proxy mỏng: quyền (đọc tệp kết quả — vai cũ hoặc lego) và bộ lọc chỉ định do
// máy chủ quyết. Máy chủ cũng kiểm lại chỉ định thuộc đúng lượt lúc tải lên.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "@/lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: Request) {
  const id = (new URL(request.url).searchParams.get("appointment_id") ?? "").trim();
  if (!UUID_RE.test(id)) {
    return NextResponse.json({ error: "Mã lịch hẹn không hợp lệ." }, { status: 400 });
  }
  return proxyJsonToBackend(
    "GET",
    `/api/v1/cskh/ket-qua/chi-dinh-cua-lich/${encodeURIComponent(id)}`,
    undefined,
  );
}
