// File Excel địa chỉ khách (kế toán rà địa chỉ sai, 11/11/2026). Proxy mỏng: quyền
// (Kế toán / Quản lý), lọc, ghi nhật ký — máy chủ quyết. Chỉ chép hai tham số lọc của
// màn Danh sách bệnh nhân, cắt độ dài; trả nguyên luồng byte.

import { getCallerAuthHeaders } from "@/lib/backend-proxy";
import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const input = new URL(request.url).searchParams;
  const q = new URLSearchParams();
  for (const [key, max] of [["q", 200], ["loc", 40]] as const) {
    const value = input.get(key);
    if (value) q.set(key, value.slice(0, max));
  }
  const headers = await getCallerAuthHeaders();
  const base = process.env.CLINIC_API_URL;
  if (!headers || !base) return NextResponse.json({ error: "Chưa đăng nhập hoặc thiếu CLINIC_API_URL" }, { status: 401 });
  const res = await fetch(`${base}/api/v1/patients/danh-sach-xlsx?${q}`, { headers, cache: "no-store" });
  return new NextResponse(res.body, { status: res.status, headers: {
    "Content-Type": res.headers.get("Content-Type") ?? "application/octet-stream",
    "Content-Disposition": res.headers.get("Content-Disposition") ?? 'attachment; filename="dia-chi-khach.xlsx"',
    "Cache-Control": "private, no-store",
  } });
}
