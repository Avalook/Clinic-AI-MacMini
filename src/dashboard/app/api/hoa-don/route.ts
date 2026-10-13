import { getCallerAuthHeaders, proxyJsonToBackend } from "@/lib/backend-proxy";
import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const input = new URL(request.url).searchParams;
  const q = new URLSearchParams();
  for (const key of ["tu", "den", "tim", "loai", "trang_thai", "ca", "co_so", "can_kiem_tra"]) {
    const value = input.get(key);
    if (value !== null) q.set(key, value.slice(0, key === "tim" ? 200 : 64));
  }
  if (input.get("xuat") !== "xlsx") return proxyJsonToBackend("GET", `/api/v1/hoa-don?${q}`, undefined);
  const headers = await getCallerAuthHeaders();
  const base = process.env.CLINIC_API_URL;
  if (!headers || !base) return NextResponse.json({ error: "Chưa đăng nhập hoặc thiếu CLINIC_API_URL" }, { status: 401 });
  const res = await fetch(`${base}/api/v1/hoa-don/xlsx?${q}`, { headers, cache: "no-store" });
  return new NextResponse(res.body, { status: res.status, headers: {
    "Content-Type": res.headers.get("Content-Type") ?? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "Content-Disposition": res.headers.get("Content-Disposition") ?? 'attachment; filename="danh-sach-hoa-don.xlsx"',
    "Cache-Control": "private, no-store",
  } });
}
