// Bàn xét nghiệm — tải tay kết quả đối tác (multipart: file, order_id) → FastAPI
// `/api/v1/xet-nghiem/ban/tai-ket-qua`. Chuyển tiếp NGUYÊN VĂN luồng byte (không nạp
// tệp vào RAM của Next — cùng cách `/api/cskh/ket-qua`). Quyền + luật ở máy chủ.

import { NextResponse } from "next/server";

import { chuyenTiepTaiLen } from "@/lib/chuyen-tiep-tai-len";

import { getCallerAuthHeaders } from "../../../../lib/backend-proxy";

const API_BASE = process.env.CLINIC_API_URL;

export async function POST(request: Request) {
  if (!API_BASE) {
    return NextResponse.json({ error: "CLINIC_API_URL chưa được cấu hình trên server." }, { status: 503 });
  }
  const headers = await getCallerAuthHeaders();
  if (!headers) return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  // PHẢI chuyển Content-Type (boundary) — thiếu thì FastAPI không đọc được thân.
  const ct = request.headers.get("content-type");
  if (ct) headers["Content-Type"] = ct;
  const cl = request.headers.get("content-length");
  if (cl) headers["Content-Length"] = cl;
  let res: { status: number; text: string };
  try {
    res = await chuyenTiepTaiLen(`${API_BASE}/api/v1/xet-nghiem/ban/tai-ket-qua`, request, headers);
  } catch {
    return NextResponse.json({ error: "Mất kết nối giữa chừng — tệp CHƯA được lưu, hãy tải lại." }, { status: 502 });
  }
  let payload: unknown = {};
  try {
    payload = res.text ? JSON.parse(res.text) : {};
  } catch {
    payload = { error: res.text || "Lỗi máy chủ" };
  }
  return NextResponse.json(payload, { status: res.status });
}
