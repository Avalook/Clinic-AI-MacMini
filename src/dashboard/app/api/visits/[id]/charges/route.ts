// What a visit owes for and what has been paid. Read-only proxy.

import { NextResponse } from "next/server";

import { getCallerAuthHeaders } from "../../../../../lib/backend-proxy";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!UUID_RE.test(id)) {
    return NextResponse.json({ error: "Mã lượt khám không hợp lệ" }, { status: 400 });
  }
  if (!API_BASE) {
    return NextResponse.json({ error: "CLINIC_API_URL chưa cấu hình" }, { status: 503 });
  }
  // Header lấy từ chỗ dùng chung. Bản cũ tự dựng ở đây và QUÊN getUser(), nên
  // sau một tiếng token hết hạn là chỗ này báo "chưa đăng nhập" trong khi mọi
  // trang khác vẫn chạy — xem getCallerAuthHeaders trong backend-proxy.ts.
  const headers = await getCallerAuthHeaders();
  if (!headers) {
    return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  }
  try {
    const res = await fetch(`${API_BASE}/api/v1/visits/${id}/charges`, {
      headers,
      cache: "no-store",
    });
    return NextResponse.json(await res.json(), { status: res.status });
  } catch {
    return NextResponse.json({ error: "Không kết nối được máy chủ" }, { status: 502 });
  }
}
