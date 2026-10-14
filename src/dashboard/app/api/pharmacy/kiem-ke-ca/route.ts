// Proxy kiểm kê đầu / cuối ca ở quầy thuốc (G6, 14/10/2026) → FastAPI.
// GET danh sách phiếu (?ngay=) hoặc nhắc thiếu kiểm (?nhac=1&ngay=&ca=) · POST mở phiếu.
// Luật (ngày/ca/số rác → 422, chốt rồi không sửa…) ở máy chủ; route chỉ chuyển tiếp.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

async function dangNhap() {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  return user;
}

export async function GET(request: Request) {
  if (!(await dangNhap())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const q = new URL(request.url).searchParams;
  const tham = new URLSearchParams();
  for (const k of ["ngay", "ca"]) {
    const v = q.get(k);
    if (v) tham.set(k, v);
  }
  const duoi = tham.toString() ? `?${tham}` : "";
  // Hai đường cố định (không ghép chuỗi trong mẫu) để test lệch-đường-dẫn đọc được.
  const goc = q.get("nhac") ? "/api/v1/pharmacy/kiem-ke-ca/nhac" : "/api/v1/pharmacy/kiem-ke-ca";
  return proxyJsonToBackend("GET", goc + duoi, undefined);
}

export async function POST(request: Request) {
  if (!(await dangNhap())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  return proxyJsonToBackend("POST", "/api/v1/pharmacy/kiem-ke-ca", body);
}
