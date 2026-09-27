import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";
import { getSupabaseServer } from "../../../../../lib/supabase-server";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Chưa đăng nhập." }, { status: 401 });
  }

  // Cửa quyền là việc của BACKEND (lab.py _TRIAGE_GUARD = quyền ghi y khoa) —
  // proxy chỉ kiểm đăng nhập (kiểm toán 27/09/2026).

  const { id } = await params;
  if (!UUID_RE.test(id)) {
    return NextResponse.json(
      { error: "Mã kết quả xét nghiệm không hợp lệ." },
      { status: 400 },
    );
  }

  return proxyJsonToBackend("POST", `/api/v1/lab/triage/${id}`, {});
}

