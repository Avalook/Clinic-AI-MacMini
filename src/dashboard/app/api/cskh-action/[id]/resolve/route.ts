// POST /api/cskh-action/{id}/resolve — đóng một việc CSKH: đã gọi / đã đóng.
//
// Trước B.4, nút "Đã gọi" trên bảng CSKH chỉ xoá dòng khỏi màn hình trong
// trình duyệt: F5 là việc quay lại, và hai người có thể gọi cùng một bệnh nhân.
// Ghi kết quả xuống là toàn bộ lý do màn hình đó tồn tại.
//
// bảng cskh_action chỉ có RLS SELECT → ghi qua FastAPI, như mọi đường ghi khác.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";
import { getClinicRole } from "../../../../../lib/clinic-session";
import { canWriteIntake } from "../../../../../lib/roles";
import { getSupabaseServer } from "../../../../../lib/supabase-server";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Mirrors RESOLUTIONS in cskh_service.py — cùng hai khoá, không hơn.
const OUTCOMES = new Set(["called", "closed"]);

interface ResolveBody {
  outcome?: string;
  note?: string;
}

export async function POST(
  request: Request,
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
  if (!canWriteIntake(role)) {
    return NextResponse.json(
      { error: "Chỉ CSKH / Lễ tân / Quản lý mới đóng việc chăm sóc." },
      { status: 403 },
    );
  }

  const { id } = await params;
  if (!UUID_RE.test(id)) {
    return NextResponse.json({ error: "Mã việc không hợp lệ." }, { status: 400 });
  }

  let body: ResolveBody;
  try {
    body = (await request.json()) as ResolveBody;
  } catch {
    return NextResponse.json({ error: "JSON không hợp lệ." }, { status: 400 });
  }

  const outcome = (body.outcome ?? "").trim();
  if (!OUTCOMES.has(outcome)) {
    return NextResponse.json(
      { error: "Kết quả xử lý không hợp lệ." },
      { status: 400 },
    );
  }

  return proxyJsonToBackend("POST", `/api/v1/cskh/actions/${id}/resolve`, {
    outcome,
    note: (body.note ?? "").trim() || null,
  });
}
