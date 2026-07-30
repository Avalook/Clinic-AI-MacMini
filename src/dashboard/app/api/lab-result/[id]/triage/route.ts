import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";
import { getClinicRole } from "../../../../../lib/clinic-session";
import { isDoctorRole } from "../../../../../lib/roles";
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

  const role = await getClinicRole();
  if (!isDoctorRole(role)) {
    return NextResponse.json(
      { error: "Chỉ bác sĩ mới phân loại kết quả xét nghiệm." },
      { status: 403 },
    );
  }

  const { id } = await params;
  if (!UUID_RE.test(id)) {
    return NextResponse.json(
      { error: "Mã kết quả xét nghiệm không hợp lệ." },
      { status: 400 },
    );
  }

  return proxyJsonToBackend("POST", `/api/v1/lab/triage/${id}`, {});
}

