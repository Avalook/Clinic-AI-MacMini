// GET /api/appointments/luoi-ngay?date=YYYY-MM-DD&doctor_ids=a,b&bo_qua_lich_id=
// Sức chứa cả lưới đặt chỗ của một ngày (mỗi bác sĩ một hàng + hàng chưa phân),
// MỘT lượt gọi. Proxy mỏng; số ghế và trần tính ở capacity_service.luoi_ngay
// (29/09/2026) — trình duyệt không tự cộng, không lấy trần chung.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

const NGAY_RE = /^\d{4}-\d{2}-\d{2}$/;

export async function GET(request: Request) {
  const sp = new URL(request.url).searchParams;
  const ngay = sp.get("date") ?? "";
  if (!NGAY_RE.test(ngay)) {
    return NextResponse.json({ error: "date phải dạng YYYY-MM-DD" }, { status: 400 });
  }
  const q = new URLSearchParams({ date: ngay });
  const bacSi = sp.get("doctor_ids");
  if (bacSi) q.set("doctor_ids", bacSi);
  const boQua = sp.get("bo_qua_lich_id");
  if (boQua) q.set("bo_qua_lich_id", boQua);
  return proxyJsonToBackend("GET", `/api/v1/appointments/luoi-ngay?${q.toString()}`, null);
}
