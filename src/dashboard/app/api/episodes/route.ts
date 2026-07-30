// PATCH /api/episodes — CSKH xác nhận vòng đời "đợt khám" (T-20260629-EPI-01).
//   { id, action: "close" | "reopen" }
//     close  = chốt đợt đã kết thúc (PENDING_CLOSE → CLOSED, close_reason cskh_confirmed)
//     reopen = BN còn theo dõi tiếp, BS quên hẹn (PENDING_CLOSE → OPEN)
// Gate = canManageAppt (CSKH / Quản lý / Trưởng ca). Chỉ thao tác từ PENDING_CLOSE.
import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole } from "../../../lib/clinic-session";
import { canManageAppt } from "../../../lib/roles";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";

interface Body {
  id?: string;
  action?: "close" | "reopen";
}

export async function PATCH(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const role = await getClinicRole();
  if (!canManageAppt(role)) {
    return NextResponse.json(
      { error: "Chỉ CSKH / Quản lý / Trưởng ca mới đóng/mở đợt khám." },
      { status: 403 },
    );
  }

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  const action = body.action;
  if (!id || (action !== "close" && action !== "reopen")) {
    return NextResponse.json(
      { error: "Thiếu id đợt khám hoặc action không hợp lệ." },
      { status: 400 },
    );
  }

  // The status change and its audit event share one transaction in FastAPI.
  return proxyJsonToBackend("PATCH", `/api/v1/episodes/${id}`, { action });
}
