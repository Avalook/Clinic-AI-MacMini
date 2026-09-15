// GET /api/appointments/cho-trong-tuan?week_start=YYYY-MM-DD — bảng Bác sĩ × tuần
// (còn chỗ / ít chỗ / đầy / nghỉ / đặt tự do). Proxy mỏng; tính ở
// capacity_service.py (16/09/2026).

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

const NGAY_RE = /^\d{4}-\d{2}-\d{2}$/;

export async function GET(request: Request) {
  const tuan = new URL(request.url).searchParams.get("week_start") ?? "";
  if (!NGAY_RE.test(tuan)) {
    return NextResponse.json({ error: "week_start phải dạng YYYY-MM-DD" }, { status: 400 });
  }
  return proxyJsonToBackend("GET", `/api/v1/appointments/cho-trong-tuan?week_start=${tuan}`, null);
}
