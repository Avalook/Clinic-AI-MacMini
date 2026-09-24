// Quầy thuốc chỉnh ĐƠN BÁN trước khi thu (Tuyền 24/09/2026) — proxy mỏng.
//
//   GET  ?visit_id=…                       → /api/v1/quay-thuoc/luot/{visit}
//   POST { thao_tac: "chon",     du_lieu: { prescription_id, mua } }
//   POST { thao_tac: "so-luong", du_lieu: { prescription_id, so_luong } }
//   POST { thao_tac: "them", id: visit, du_lieu: { dong: [...] } }
//
// Quyền (Thu tiền thuốc) và mọi luật nằm ở FastAPI; proxy giữ nguyên mã lỗi.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../lib/backend-proxy";
import { getSupabaseServer } from "../../../lib/supabase-server";

const UUID_RE = /^[0-9a-f-]{36}$/i;

async function coPhien(): Promise<boolean> {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return Boolean(user);
}

export async function GET(request: Request) {
  if (!(await coPhien())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const visit = new URL(request.url).searchParams.get("visit_id") ?? "";
  if (!UUID_RE.test(visit)) {
    return NextResponse.json({ error: "Mã lượt khám không hợp lệ" }, { status: 400 });
  }
  return proxyJsonToBackend("GET", `/api/v1/quay-thuoc/luot/${visit}`, undefined);
}

export async function POST(request: Request) {
  if (!(await coPhien())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  let than: { thao_tac?: unknown; id?: unknown; du_lieu?: unknown };
  try {
    than = await request.json();
  } catch {
    return NextResponse.json({ error: "Dữ liệu gửi lên không đọc được." }, { status: 400 });
  }
  const duLieu = (than.du_lieu ?? {}) as Record<string, unknown>;
  if (than.thao_tac === "chon") {
    return proxyJsonToBackend("POST", "/api/v1/quay-thuoc/chon", duLieu);
  }
  if (than.thao_tac === "so-luong") {
    return proxyJsonToBackend("POST", "/api/v1/quay-thuoc/so-luong", duLieu);
  }
  if (than.thao_tac === "them") {
    const id = typeof than.id === "string" ? than.id : "";
    if (!UUID_RE.test(id)) {
      return NextResponse.json({ error: "Mã lượt khám không hợp lệ" }, { status: 400 });
    }
    return proxyJsonToBackend("POST", `/api/v1/quay-thuoc/luot/${id}/them`, duLieu);
  }
  return NextResponse.json({ error: "Thao tác không hợp lệ." }, { status: 400 });
}
