// /api/day-noi — khối chỉnh dây nối nghiệp vụ (nhóm 5, 24/09/2026).
//
// Chỉ chuyển tiếp. Quyền (`config.wiring.manage`) và mọi luật nằm ở FastAPI
// (`day_noi_service.py`) — lớp này không tự suy quyền từ vai.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../lib/backend-proxy";
import { getSupabaseServer } from "../../../lib/supabase-server";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function coPhien(): Promise<boolean> {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return Boolean(user);
}

export async function GET() {
  if (!(await coPhien())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  return proxyJsonToBackend("GET", "/api/v1/day-noi", undefined);
}

export async function POST(request: Request) {
  if (!(await coPhien())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const than = (await request.json().catch(() => null)) as
    | { thao_tac?: string; id?: string; du_lieu?: unknown }
    | null;
  const id = typeof than?.id === "string" ? than.id : "";
  const du = than?.du_lieu ?? {};
  switch (than?.thao_tac) {
    case "day":
      return proxyJsonToBackend("PATCH", "/api/v1/day-noi/day", du);
    case "chuong":
      return proxyJsonToBackend("PUT", "/api/v1/day-noi/chuong", du);
    case "vi-tri-moi":
      return proxyJsonToBackend("POST", "/api/v1/day-noi/vi-tri", du);
    case "loai-kham":
      if (!UUID_RE.test(id)) break;
      return proxyJsonToBackend("PATCH", `/api/v1/day-noi/loai-kham/${id}`, du);
    case "vi-tri":
      if (!UUID_RE.test(id)) break;
      return proxyJsonToBackend("PATCH", `/api/v1/day-noi/vi-tri/${id}`, du);
  }
  return NextResponse.json(
    { error: "BAD_REQUEST", message: "Thao tác không hợp lệ." },
    { status: 400 },
  );
}
