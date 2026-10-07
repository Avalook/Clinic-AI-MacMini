// /api/ho-so-kham — hồ sơ khám của MỘT lượt: dịch vụ của lượt (đổi trong hồ
// sơ, 07/10/2026). Chỉ chuyển tiếp; quyền + luật ở backend
// (`services/ho_so_dich_vu.py`, SO-LUAT Phần 3).
//
//   GET  ?visit_id=…&xem=dich-vu
//   POST { thao_tac: "doi-dich-vu", visit_id, service_type_id }

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";
import { getSupabaseServer } from "../../../lib/supabase-server";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function daDangNhap(): Promise<boolean> {
  const db = await getSupabaseServer();
  const {
    data: { user },
  } = await db.auth.getUser();
  return Boolean(user);
}

export async function GET(request: Request) {
  if (!(await daDangNhap())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const sp = new URL(request.url).searchParams;
  const vid = sp.get("visit_id") ?? "";
  if (!UUID.test(vid)) return NextResponse.json({ error: "Thiếu mã lượt khám." }, { status: 400 });
  return proxyJsonToBackend("GET", `/api/v1/ho-so-kham/${vid}/dich-vu`, undefined);
}

export async function POST(request: Request) {
  if (!(await daDangNhap())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const body = (await request.json().catch(() => null)) as {
    thao_tac?: string;
    visit_id?: string;
    service_type_id?: string;
  } | null;
  const vid = body?.visit_id ?? "";
  if (body?.thao_tac !== "doi-dich-vu" || !UUID.test(vid)) {
    return NextResponse.json({ error: "Yêu cầu không hợp lệ." }, { status: 400 });
  }
  return proxyJsonToBackend("POST", `/api/v1/ho-so-kham/${vid}/doi-dich-vu`, {
    service_type_id: body.service_type_id ?? null,
  });
}
