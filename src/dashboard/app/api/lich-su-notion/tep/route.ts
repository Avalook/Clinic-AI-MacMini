// Tệp kết quả (PDF) của một xét nghiệm cũ nhập từ Notion — CHẢY THEO LUỒNG,
// cùng cách với `/api/cskh/ket-qua/[tepId]/noi-dung` (không đọc cả tệp vào RAM,
// `nosniff`, không cache vì là dữ liệu bệnh nhân).
//
//   GET ?xn=<id xét nghiệm cũ>&i=<số thứ tự tệp>[&tai=1]

import { NextResponse } from "next/server";

import { getCallerAuthHeaders } from "@/lib/backend-proxy";

const API_BASE = process.env.CLINIC_API_URL;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: Request) {
  if (!API_BASE) {
    return NextResponse.json(
      { error: "CLINIC_API_URL chưa được cấu hình trên server." },
      { status: 503 },
    );
  }
  const auth = await getCallerAuthHeaders();
  if (!auth) return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });

  const q = new URL(request.url).searchParams;
  const xn = q.get("xn") ?? "";
  const i = q.get("i") ?? "";
  if (!UUID_RE.test(xn) || !/^\d{1,3}$/.test(i)) {
    return NextResponse.json({ error: "Tham số không hợp lệ." }, { status: 400 });
  }
  let res: Response;
  try {
    res = await fetch(
      `${API_BASE}/api/v1/lich-su-notion/xet-nghiem/${xn}/tep/${i}${q.get("tai") === "1" ? "?tai=1" : ""}`,
      { headers: { ...auth }, cache: "no-store" },
    );
  } catch {
    return NextResponse.json({ error: "Không kết nối được máy chủ xử lý" }, { status: 502 });
  }
  const ra: Record<string, string> = {
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "private, no-store",
  };
  for (const h of ["content-type", "content-length", "content-disposition"]) {
    const v = res.headers.get(h);
    if (v) ra[h] = v;
  }
  return new Response(res.body, { status: res.status, headers: ra });
}
