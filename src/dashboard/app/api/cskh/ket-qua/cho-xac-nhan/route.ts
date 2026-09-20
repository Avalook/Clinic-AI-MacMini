// Danh sách tệp kết quả external đang chờ xác nhận (CHO_XAC_NHAN).
// Proxy mỏng tới FastAPI GET /api/v1/cskh/ket-qua/cho-xac-nhan.
// Fail-closed: thiếu capability ket_qua.xac_nhan -> 403.

import { NextResponse } from "next/server";
import { getCallerAuthHeaders } from "@/lib/backend-proxy";

const API_BASE = process.env.CLINIC_API_URL;

export async function GET() {
  if (!API_BASE) {
    return NextResponse.json(
      { error: "CLINIC_API_URL chưa được cấu hình trên server." },
      { status: 503 },
    );
  }
  const headers = await getCallerAuthHeaders();
  if (!headers) {
    return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1/cskh/ket-qua/cho-xac-nhan`, {
      method: "GET",
      headers,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { error: "Không kết nối được tới máy chủ dịch vụ." },
      { status: 502 },
    );
  }

  const text = await res.text();
  let data: unknown = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { error: text || "Lỗi máy chủ" };
  }

  return NextResponse.json(data, { status: res.status });
}
