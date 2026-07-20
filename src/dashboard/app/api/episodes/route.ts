// PATCH /api/episodes — CSKH xác nhận vòng đời "đợt khám" (T-20260629-EPI-01).
//   { id, action: "close" | "reopen" }
//     close  = chốt đợt đã kết thúc (PENDING_CLOSE → CLOSED, close_reason cskh_confirmed)
//     reopen = BN còn theo dõi tiếp, BS quên hẹn (PENDING_CLOSE → OPEN)
// Gate = canManageAppt (CSKH / Quản lý / Trưởng ca). Chỉ thao tác từ PENDING_CLOSE.
import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getSupabaseService } from "../../../lib/supabase-service";
import { getClinicRole, getClinicStaffId } from "../../../lib/clinic-session";
import { canManageAppt } from "../../../lib/roles";
import { logEvent } from "../../../lib/event-log";

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
  const staffId = await getClinicStaffId();

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

  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }

  const nowIso = new Date().toISOString();
  const patch =
    action === "close"
      ? { status: "CLOSED", closed_at: nowIso, close_reason: "cskh_confirmed", updated_at: nowIso }
      : { status: "OPEN", closed_at: null, close_reason: null, updated_at: nowIso };

  // Chỉ chuyển từ PENDING_CLOSE (race guard) → 0 row khớp nếu ai đó vừa xử lý.
  const { data: updated, error } = await db
    .from("care_episode")
    .update(patch)
    .eq("id", id)
    .eq("status", "PENDING_CLOSE")
    .select("id");
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!updated || updated.length === 0) {
    return NextResponse.json(
      { error: "Đợt khám không còn chờ xác nhận (đã được xử lý)." },
      { status: 409 },
    );
  }

  await logEvent(db, {
    event_type: action === "close" ? "episode.closed" : "episode.reopened",
    aggregate_type: "care_episode",
    aggregate_id: id,
    payload: { episode_id: id, status: patch.status },
    metadata: {
      clinic_role: role,
      clinic_staff_id: staffId,
      actor_auth_user_id: user.id,
      origin: `dashboard:episode-${action}`,
    },
  });

  return NextResponse.json({ ok: true, status: patch.status });
}
