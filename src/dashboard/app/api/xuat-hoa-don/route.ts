import { getCallerAuthHeaders, proxyJsonToBackend } from "@/lib/backend-proxy";
import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const input = new URL(request.url).searchParams;
  const q = new URLSearchParams();
  for (const key of ["tu", "den", "loai", "co_so", "che_do", "ghi_giam_gia"]) {
    const value = input.get(key);
    if (value !== null) q.set(key, value.slice(0, 64));
  }
  // Sửa tay thuế từng dòng ({"id dòng": "mã"}) — máy chủ kiểm độ dài / kiểu, rác thì bỏ.
  const ghiDe = input.get("ghi_de");
  if (ghiDe !== null) q.set("ghi_de", ghiDe.slice(0, 60000));
  if (input.get("xuat") !== "xlsx") return proxyJsonToBackend("GET", `/api/v1/hoa-don/xuat?${q}`, undefined);
  const headers = await getCallerAuthHeaders();
  const base = process.env.CLINIC_API_URL;
  if (!headers || !base) return NextResponse.json({ error: "Chưa đăng nhập hoặc thiếu CLINIC_API_URL" }, { status: 401 });
  const res = await fetch(`${base}/api/v1/hoa-don/xuat/xlsx?${q}`, { headers, cache: "no-store" });
  return new NextResponse(res.body, { status: res.status, headers: {
    "Content-Type": res.headers.get("Content-Type") ?? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "Content-Disposition": res.headers.get("Content-Disposition") ?? 'attachment; filename="hoa-don-gtgt.xlsx"',
    "Cache-Control": "private, no-store",
  } });
}
