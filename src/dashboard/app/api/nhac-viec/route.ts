// /api/nhac-viec — tự nhắc việc cho chính mình (nhóm 5, 24/09/2026).
// Chỉ chuyển tiếp; mọi luật ở FastAPI (`nhac_viec_service.py`).

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

export async function GET(request: Request) {
  if (!(await coPhien())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const khach = new URL(request.url).searchParams.get("khach") ?? "";
  return proxyJsonToBackend(
    "GET",
    UUID_RE.test(khach) ? `/api/v1/nhac-viec?clinic_patient_id=${khach}` : "/api/v1/nhac-viec",
    undefined,
  );
}

export async function POST(request: Request) {
  if (!(await coPhien())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const than = (await request.json().catch(() => null)) as
    | { thao_tac?: string; id?: string; du_lieu?: unknown }
    | null;
  if (than?.thao_tac === "tao") {
    return proxyJsonToBackend("POST", "/api/v1/nhac-viec", than.du_lieu ?? {});
  }
  if (than?.thao_tac === "xong" && typeof than.id === "string" && UUID_RE.test(than.id)) {
    return proxyJsonToBackend("POST", `/api/v1/nhac-viec/${than.id}/xong`, {});
  }
  return NextResponse.json(
    { error: "BAD_REQUEST", message: "Thao tác không hợp lệ." },
    { status: 400 },
  );
}
