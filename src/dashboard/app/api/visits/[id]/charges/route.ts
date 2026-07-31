// What a visit owes for and what has been paid. Read-only proxy.

import { NextResponse } from "next/server";

import { getSupabaseServer } from "../../../../../lib/supabase-server";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!UUID_RE.test(id)) {
    return NextResponse.json({ error: "Mã lượt khám không hợp lệ" }, { status: 400 });
  }
  if (!API_BASE) {
    return NextResponse.json({ error: "CLINIC_API_URL chưa cấu hình" }, { status: 503 });
  }
  const supabase = await getSupabaseServer();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.access_token) {
    return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  }
  const headers: Record<string, string> = {
    Authorization: `Bearer ${session.access_token}`,
  };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;
  try {
    const res = await fetch(`${API_BASE}/api/v1/visits/${id}/charges`, {
      headers,
      cache: "no-store",
    });
    return NextResponse.json(await res.json(), { status: res.status });
  } catch {
    return NextResponse.json({ error: "Không kết nối được máy chủ" }, { status: 502 });
  }
}
