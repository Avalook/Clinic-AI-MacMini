// Đọc một phiếu kiểm kê ca (G6) — chuyển tiếp xuống FastAPI.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../../lib/supabase-server";
import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const { id } = await params;
  if (!UUID_RE.test(id)) return NextResponse.json({ error: "Mã phiếu không hợp lệ" }, { status: 400 });
  return proxyJsonToBackend("GET", `/api/v1/pharmacy/kiem-ke-ca/${id}`, undefined);
}
