// Dịch vụ đang tích cho lượt khám (Tuyền chốt 15/09/2026: chỉ định là danh sách
// bác sĩ tích). Proxy mỏng.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!UUID_RE.test(id)) {
    return NextResponse.json({ error: "Mã lượt khám không hợp lệ" }, { status: 400 });
  }
  return proxyJsonToBackend("GET", `/api/v1/visits/${id}/service-orders/current`, null);
}
