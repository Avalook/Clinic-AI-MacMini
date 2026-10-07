// /api/ho-so-kham — hồ sơ khám của MỘT lượt: dịch vụ của lượt (đổi trong hồ
// sơ, 07/10/2026). Chỉ chuyển tiếp; quyền + luật ở backend
// (`services/ho_so_dich_vu.py`, SO-LUAT Phần 3).
//
//   GET  ?visit_id=…&xem=dich-vu | dieu-tri | ghi-chu   (dieu-tri = thẻ chỉ định
//        điều trị; ghi-chu = ô chữ tự do lượt "Khác")
//   PUT  { visit_id, noi_dung, phien_ban }   (ô chữ tự do — thêm một phiên bản)
//   POST { thao_tac: "doi-dich-vu", visit_id, service_type_id }
//   POST { thao_tac: "ban-kham", visit_id, order_id, lenh, expected_execution_revision,
//          attempt_id }   (Làm tại bàn khám / Xong / hoàn tác — khối 4 Điều trị)

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
  const xemHoi = sp.get("xem");
  const xem = xemHoi === "dieu-tri" || xemHoi === "ghi-chu" ? xemHoi : "dich-vu";
  if (!UUID.test(vid)) return NextResponse.json({ error: "Thiếu mã lượt khám." }, { status: 400 });
  return proxyJsonToBackend("GET", `/api/v1/ho-so-kham/${vid}/${xem}`, undefined);
}

export async function PUT(request: Request) {
  if (!(await daDangNhap())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const body = (await request.json().catch(() => null)) as {
    visit_id?: string;
    noi_dung?: unknown;
    phien_ban?: unknown;
  } | null;
  const vid = body?.visit_id ?? "";
  if (!UUID.test(vid)) return NextResponse.json({ error: "Yêu cầu không hợp lệ." }, { status: 400 });
  return proxyJsonToBackend("PUT", `/api/v1/ho-so-kham/${vid}/ghi-chu`, {
    noi_dung: typeof body?.noi_dung === "string" ? body.noi_dung : "",
    phien_ban: typeof body?.phien_ban === "number" ? body.phien_ban : 0,
  });
}

export async function POST(request: Request) {
  if (!(await daDangNhap())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const body = (await request.json().catch(() => null)) as {
    thao_tac?: string;
    visit_id?: string;
    service_type_id?: string;
    order_id?: string;
    lenh?: string;
    expected_execution_revision?: number;
    attempt_id?: string | null;
  } | null;
  const vid = body?.visit_id ?? "";
  if (!UUID.test(vid)) return NextResponse.json({ error: "Yêu cầu không hợp lệ." }, { status: 400 });
  if (body?.thao_tac === "doi-dich-vu") {
    return proxyJsonToBackend("POST", `/api/v1/ho-so-kham/${vid}/doi-dich-vu`, {
      service_type_id: body.service_type_id ?? null,
    });
  }
  // Thẻ chỉ định điều trị: lam | xong | huy-lam | hoan-tac-xong (máy chủ kiểm).
  const oid = body?.order_id ?? "";
  const lenh = body?.lenh ?? "";
  if (body?.thao_tac !== "ban-kham" || !UUID.test(oid) || !/^[a-z-]{2,20}$/.test(lenh)) {
    return NextResponse.json({ error: "Yêu cầu không hợp lệ." }, { status: 400 });
  }
  return proxyJsonToBackend(
    "POST",
    `/api/v1/ho-so-kham/${vid}/dieu-tri/${oid}/${lenh}`,
    {
      expected_execution_revision: body.expected_execution_revision ?? 0,
      attempt_id: body.attempt_id ?? null,
    },
    request.headers.get("Idempotency-Key") ?? undefined,
  );
}
