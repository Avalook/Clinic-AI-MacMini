// Appointment booking for CSKH / Lễ tân. Same access model + service-role
// write path as /api/patients.
//
//   POST { clinic_patient_id, doctor_id?, service_type_id, location_id,
//          slot_start, slot_end, booking_channel? }
//     → { ok: true, appointment_id }
//
// The DB has an exclusion constraint (appointment_no_doctor_overlap) — a
// doctor double-book surfaces as a friendly 409.
//
//   PATCH { id, action: "confirm" | "decline" }   (DOCTOR only, own appt)
//     → { ok: true, status }
//   Two-step confirmation: CSKH confirms WITH THE PATIENT (cskh_confirm:
//   SCHEDULED→CSKH_CONFIRMED) but the slot still awaits the doctor. Confirm:
//   SCHEDULED|CSKH_CONFIRMED→CONFIRMED. Decline: SCHEDULED|CSKH_CONFIRMED→
//   DOCTOR_DECLINED (keeps doctor_id for history; surfaces to CSKH in the
//   "Đã huỷ / Từ chối" column + the declined-appointments notice in the layout).

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getSupabaseService } from "../../../lib/supabase-service";
import { vnTodayRangeUtc } from "../../../lib/datetime";
import { getClinicRole, getClinicStaffId } from "../../../lib/clinic-session";
import {
  canWriteIntake,
  isDoctorRole,
  canManageAppt,
  canCheckin,
} from "../../../lib/roles";
import { logEvent } from "../../../lib/event-log";
import { weekStartOf } from "../../../lib/roster";
import {
  suggestLoad,
  type PatientKind,
} from "../../../lib/capacity";
import {
  slotBucketRange,
  isWalkinChannel,
  isDeadStatus,
  REGULAR_CAP,
  WALKIN_CAP,
} from "../../../lib/slot-capacity";

interface Body {
  clinic_patient_id?: string;
  doctor_id?: string;
  service_type_id?: string;
  location_id?: string;
  slot_start?: string;
  slot_end?: string;
  booking_channel?: string;
  queue_number?: string;
  // Capacity Phase 1 (T-20260629-CAP-01) — CSKH nhập tay (DEC-3).
  patient_kind?: string;
  thanh_min?: number;
  sono_min?: number;
  need_sono?: boolean;
}

type DbClient = NonNullable<ReturnType<typeof getSupabaseService>>;

// Tìm lịch của bác sĩ ĐANG TRÙNG khung giờ [slotStart, slotEnd) (bỏ CANCELLED/
// NO_SHOW; loại trừ chính lịch đang sửa). Có trùng → trả câu báo RÕ "bận khung
// giờ HH:MM–HH:MM ngày dd/mm" + tên bác sĩ; không trùng → null. Best-effort: lỗi
// truy vấn trả null để rơi về thông báo chung (ràng buộc DB vẫn là chốt chặn cuối).
async function doctorConflictMessage(
  db: DbClient,
  doctorId: string,
  slotStart: string,
  slotEnd: string,
  excludeId?: string,
): Promise<string | null> {
  try {
    let q = db
      .from("appointment")
      .select("id, slot_start, slot_end, status")
      .eq("doctor_id", doctorId)
      .lt("slot_start", slotEnd)
      .gt("slot_end", slotStart);
    if (excludeId) q = q.neq("id", excludeId);
    const { data } = await q;
    const activeAppts = (
      (data as
        | { slot_start: string; slot_end: string; status: string }[]
        | null) ?? []
    ).filter((r) => r.status !== "CANCELLED" && r.status !== "NO_SHOW");

    if (activeAppts.length < 6) return null;

    const { data: doc } = await db
      .from("staff")
      .select("full_name")
      .eq("id", doctorId)
      .maybeSingle();
    const name = (doc as { full_name: string } | null)?.full_name;
    const hhmm = (iso: string) =>
      new Date(iso).toLocaleTimeString("vi-VN", {
        timeZone: "Asia/Ho_Chi_Minh",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
    const day = new Date(slotStart).toLocaleDateString("vi-VN", {
      timeZone: "Asia/Ho_Chi_Minh",
      day: "2-digit",
      month: "2-digit",
    });
    return `Bác sĩ${name ? ` ${name}` : ""} đã đạt giới hạn 6 lịch hẹn trong khung giờ ${hhmm(slotStart)}–${hhmm(slotEnd)} ngày ${day}. Vui lòng chọn khung giờ khác.`;
  } catch {
    return null;
  }
}

// Luật "2 + 1" mỗi khung 15' (sơ đồ rạp chiếu phim, 2026-07-02): mỗi BÁC SĨ ×
// KHUNG 15' chỉ có 2 chỗ kênh thường (BN1/BN2) + 1 chỗ vãng lai (WALK_IN).
// Đếm theo slot_start rơi TRONG khung chứa ứng viên (khớp cách UI vẽ lưới);
// hàng "Chưa phân bác sĩ" (doctor_id null) giới hạn y hệt. excludeId để dùng
// cho reschedule/reassign (không tự đếm chính mình). Trả câu lỗi tiếng Việt
// khi hết chỗ; null = còn chỗ. Best-effort: lỗi truy vấn → null (fail-open,
// đã còn net 6-overlap ở DB + engine ngân sách CAP-01).
async function slotCapMessage(
  db: DbClient,
  doctorId: string | null,
  slotStart: string,
  bookingChannel: string,
  excludeId?: string,
): Promise<string | null> {
  try {
    const { startUtc, endUtc } = slotBucketRange(slotStart);
    let q = db
      .from("appointment")
      .select("id, booking_channel, status")
      .gte("slot_start", startUtc)
      .lt("slot_start", endUtc);
    q = doctorId ? q.eq("doctor_id", doctorId) : q.is("doctor_id", null);
    if (excludeId) q = q.neq("id", excludeId);
    const { data, error } = await q;
    if (error) return null;
    let regular = 0;
    let walkin = 0;
    for (const r of (data as
      | { booking_channel: string | null; status: string }[]
      | null) ?? []) {
      if (isDeadStatus(r.status)) continue;
      if (isWalkinChannel(r.booking_channel)) walkin += 1;
      else regular += 1;
    }
    const hhmm = (iso: string) =>
      new Date(iso).toLocaleTimeString("vi-VN", {
        timeZone: "Asia/Ho_Chi_Minh",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
    const window = `${hhmm(startUtc)}–${hhmm(endUtc)}`;
    if (isWalkinChannel(bookingChannel)) {
      if (walkin >= WALKIN_CAP) {
        return `Khung ${window} đã có khách vãng lai — chuyển khách sang khung 15 phút kế tiếp.`;
      }
      return null;
    }
    if (regular >= REGULAR_CAP) {
      return `Khung ${window} đã đủ ${REGULAR_CAP} chỗ đặt hẹn (BN1, BN2) — chọn khung khác. Chỗ thứ 3 chỉ dành cho khách vãng lai.`;
    }
    return null;
  } catch {
    return null;
  }
}

// "Đợt khám" (care_episode, T-20260629-EPI-01) — gắn lượt hẹn vừa tạo vào một đợt theo
// trạng thái + lựa chọn tải của CSKH. Best-effort: mọi lỗi (kể cả bảng chưa migrate trên
// DB này) chỉ log, KHÔNG chặn đặt lịch (đợt là proxy tải, không phải khoá pháp lý).
//   patient_kind === 'NEW'  → đóng đợt sống cũ (nếu có) vì là vấn đề mới, MỞ đợt mới.
//   patient_kind === 'RETURN' (hoặc null + có đợt sống) → gắn vào đợt sống; PENDING_CLOSE
//                            được mở lại (BS định đóng nhưng BN quay lại = vẫn tiếp diễn).
//   null + không có đợt sống → coi như NEW (mở đợt mới).
async function attachEpisode(
  db: DbClient,
  args: {
    appointmentId: string;
    clinic_patient_id: string;
    service_type_id: string;
    patient_kind: PatientKind | null;
  },
): Promise<void> {
  try {
    const { data: liveRaw } = await db
      .from("care_episode")
      .select("id, status")
      .eq("clinic_patient_id", args.clinic_patient_id)
      .eq("service_type_id", args.service_type_id)
      .neq("status", "CLOSED")
      .limit(1)
      .maybeSingle();
    const live = liveRaw as { id: string; status: string } | null;
    const nowIso = new Date().toISOString();
    const effectiveKind: PatientKind =
      args.patient_kind ?? (live ? "RETURN" : "NEW");

    if (effectiveKind === "RETURN" && live) {
      // Tiếp tục đợt đang sống. Mở lại nếu BS đã đặt chờ-đóng.
      const patch: Record<string, unknown> = { last_visit_at: nowIso, updated_at: nowIso };
      if (live.status === "PENDING_CLOSE") patch.status = "OPEN";
      await db.from("care_episode").update(patch).eq("id", live.id);
      await db.from("appointment").update({ episode_id: live.id }).eq("id", args.appointmentId);
      return;
    }

    // NEW (hoặc RETURN nhưng không còn đợt sống) → mở đợt mới. Nếu là vấn đề mới mà còn
    // đợt sống cũ → đóng đợt cũ trước (giữ partial-unique 1 đợt sống / (BN, dịch vụ)).
    if (live) {
      await db
        .from("care_episode")
        .update({ status: "CLOSED", closed_at: nowIso, close_reason: "new_problem", updated_at: nowIso })
        .eq("id", live.id);
    }
    const { data: created } = await db
      .from("care_episode")
      .insert({
        clinic_patient_id: args.clinic_patient_id,
        service_type_id: args.service_type_id,
        status: "OPEN",
        opened_appointment_id: args.appointmentId,
        last_visit_at: nowIso,
      })
      .select("id")
      .single();
    if (created?.id) {
      await db.from("appointment").update({ episode_id: created.id }).eq("id", args.appointmentId);
    }
  } catch (e) {
    console.error("attachEpisode lỗi (bỏ qua, không chặn đặt lịch):", e);
  }
}

export async function GET(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const { searchParams } = new URL(request.url);
  const date = searchParams.get("date"); // YYYY-MM-DD
  const doctorId = searchParams.get("doctor_id");

  if (!date) {
    return NextResponse.json({ error: "Missing date parameter" }, { status: 400 });
  }

  // Parse start and end of day in UTC based on VN timezone
  const startOfDay = new Date(`${date}T00:00:00+07:00`).toISOString();
  const endOfDay = new Date(`${date}T23:59:59+07:00`).toISOString();

  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }

  let query = db
    .from("appointment")
    .select("id, slot_start, queue_number, status, doctor_id, booking_channel")
    .gte("slot_start", startOfDay)
    .lte("slot_start", endOfDay)
    .not("status", "eq", "CANCELLED")
    .not("status", "eq", "NO_SHOW");

  if (doctorId) {
    query = query.eq("doctor_id", doctorId);
  }

  const { data, error } = await query;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ appointments: data });
}

export async function POST(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const role = await getClinicRole();
  if (!canWriteIntake(role)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }
  const staffId = await getClinicStaffId();

  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const clinic_patient_id = (body.clinic_patient_id ?? "").trim();
  const service_type_id = (body.service_type_id ?? "").trim();
  const location_id = (body.location_id ?? "").trim();
  const slot_start = (body.slot_start ?? "").trim();
  const slot_end = (body.slot_end ?? "").trim();
  if (!clinic_patient_id || !service_type_id || !location_id) {
    return NextResponse.json(
      { error: "Thiếu bệnh nhân / dịch vụ / cơ sở." },
      { status: 400 },
    );
  }
  if (!slot_start || !slot_end) {
    return NextResponse.json({ error: "Thiếu giờ hẹn." }, { status: 400 });
  }
  if (new Date(slot_end).getTime() <= new Date(slot_start).getTime()) {
    return NextResponse.json(
      { error: "Giờ kết thúc phải sau giờ bắt đầu." },
      { status: 400 },
    );
  }

  const doctor_id = (body.doctor_id ?? "").trim() || null;
  const rawChannel = (body.booking_channel ?? "").trim();
  const booking_channel = rawChannel || "WALK_IN";
  const queue_number = (body.queue_number ?? "").trim() || null;

  // Capacity Phase 1 — tải/ca. CSKH nhập tay; nếu thiếu thì GỢI Ý theo loại khách (DEC-3).
  const rawKind = (body.patient_kind ?? "").trim().toUpperCase();
  const patient_kind: PatientKind | null =
    rawKind === "NEW" || rawKind === "RETURN" ? (rawKind as PatientKind) : null;
  const need_sono =
    typeof body.need_sono === "boolean" ? body.need_sono : null;
  const suggested =
    patient_kind != null
      ? suggestLoad(patient_kind, need_sono ?? false)
      : { thanh_min: null as number | null, sono_min: null as number | null };
  const thanh_min =
    typeof body.thanh_min === "number" ? body.thanh_min : suggested.thanh_min;
  const sono_min =
    typeof body.sono_min === "number" ? body.sono_min : suggested.sono_min;

  // KHÁCH TỚI TRỰC TIẾP cho HÔM NAY → tạo lịch là ĐÃ CHECK-IN luôn (PK chốt: walk-in
  // auto check-in — khách đã có mặt ở quầy, không phải chờ "Gọi xác nhận"), tự cấp
  // số thứ tự nếu chưa nhập. CHỈ áp khi kênh = WALK_IN ĐƯỢC CHỌN RÕ (rawChannel, không
  // phải mặc định rỗng) + slot TRONG NGÀY HÔM NAY — để KHÔNG vô tình check-in lịch
  // tương lai hay lịch đặt qua điện thoại quên chọn kênh.
  const { startUtc: todayStart, endUtc: todayEnd } = vnTodayRangeUtc();
  const slotMs = new Date(slot_start).getTime();
  const slotIsToday =
    slotMs >= Date.parse(todayStart) && slotMs < Date.parse(todayEnd);
  const autoCheckin = rawChannel === "WALK_IN" && slotIsToday;
  const initialStatus = autoCheckin ? "CHECKED_IN" : "SCHEDULED";
  // When an auto-check-in has no manual number, the DB trigger assigns it
  // under the same per-day advisory lock used by PATCH check-in.

  // Chặn TRÙNG GIỜ bác sĩ NGAY (báo rõ khung giờ bận) — không để khách đặt được
  // rồi mới văng lỗi. Ràng buộc DB (appointment_no_doctor_overlap) vẫn là chốt cuối.
  if (doctor_id) {
    const busy = await doctorConflictMessage(db, doctor_id, slot_start, slot_end);
    if (busy) return NextResponse.json({ error: busy }, { status: 409 });
  }

  // Luật 2+1 mỗi khung 15' — chặn TRƯỚC insert (kể cả khung "Chưa phân bác sĩ").
  {
    const full = await slotCapMessage(db, doctor_id, slot_start, booking_channel);
    if (full) return NextResponse.json({ error: full }, { status: 409 });
  }

  // Capacity Phase 1 (T-20260629-CAP-01) — engine ngân sách phút/khung-GIỜ KHÔNG
  // còn chặn đặt lịch: luật đặt chỗ chính thức là "2+1 mỗi khung 15'"
  // (slotCapMessage ở trên) — CSKH đặt 2 chỗ BN1/BN2, chỗ 3 để khách vãng lai.
  // Ngân sách/giờ của CAP-01 (online_quota_min ~28' cho BS Thành khung 17h) CHẶT
  // HƠN luật ghế 2+1 nên từng chặn oan người thứ 2 (full_online) dù lưới còn chỗ.
  // Giữ engine capacity.ts + block_budget để Phase 1.5 dùng làm CẢNH BÁO MỀM /
  // advisory-lock; net cứng cuối vẫn là ràng buộc 6-overlap ở DB (DEC-1).

  const { data, error } = await db
    .from("appointment")
    .insert({
      clinic_patient_id,
      doctor_id,
      service_type_id,
      location_id,
      slot_start,
      slot_end,
      booking_channel,
      queue_number,
      status: initialStatus,
      patient_kind,
      thanh_min,
      sono_min,
      need_sono,
    })
    .select("id")
    .single();

  if (error) {
    // 23P01 = exclusion_violation (doctor slot overlap) — đua ghi: báo rõ giờ bận.
    if (error.code === "23P01") {
      const busy = doctor_id
        ? await doctorConflictMessage(db, doctor_id, slot_start, slot_end)
        : null;
      return NextResponse.json(
        { error: busy ?? "Bác sĩ đã có lịch trùng khung giờ này." },
        { status: 409 },
      );
    }
    // 23514 = check_violation raised by the atomic 2+1 slot-capacity trigger
    // (DB net for the overbook race; see migration 20260714000002). Surface the
    // Vietnamese message as a clean 409 instead of a 500.
    if (error.code === "23514" && /Khung giờ đã đầy/.test(error.message)) {
      return NextResponse.json({ error: error.message }, { status: 409 });
    }
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  // Đợt khám (T-20260629-EPI-01) — mở/đóng/gắn đợt theo loại khám. Best-effort.
  await attachEpisode(db, {
    appointmentId: data.id,
    clinic_patient_id,
    service_type_id,
    patient_kind,
  });

  // Append-only audit trail for this booking (best-effort, see event-log.ts).
  await logEvent(db, {
    event_type: "appointment.created",
    aggregate_type: "appointment",
    aggregate_id: data.id,
    payload: {
      appointment_id: data.id,
      clinic_patient_id,
      doctor_id,
      service_type_id,
      location_id,
      slot_start,
      slot_end,
      booking_channel,
      status: initialStatus,
    },
    metadata: {
      clinic_role: role,
      clinic_staff_id: staffId,
      actor_auth_user_id: user.id,
      origin: "dashboard:appointment-booking",
    },
  });

  // Walk-in hôm nay đã tạo thẳng CHECKED_IN → ghi thêm 1 vết check-in (giữ audit
  // trail đồng nhất với luồng Lễ tân bấm "Check-in" ở PATCH). Best-effort.
  if (autoCheckin) {
    await logEvent(db, {
      event_type: "appointment.checked_in",
      aggregate_type: "appointment",
      aggregate_id: data.id,
      payload: {
        appointment_id: data.id,
        clinic_patient_id,
        slot_start,
        queue_number,
        status: "CHECKED_IN",
        auto_walk_in: true,
      },
      metadata: {
        clinic_role: role,
        clinic_staff_id: staffId,
        actor_auth_user_id: user.id,
        origin: "dashboard:appointment-walkin-autocheckin",
      },
    });

    // …và MỞ visit OPEN ngay (giống luồng PATCH check-in) → BN hiện trên bảng
    // "Trạng thái BN buổi khám hôm nay" từ lúc tạo walk-in. Best-effort.
    const { error: vErr } = await db.from("visit").insert({
      clinic_patient_id,
      appointment_id: data.id,
      attending_doctor_id: doctor_id,
      status: "OPEN",
      checked_in_at: new Date().toISOString(),
    });
    if (vErr && vErr.code !== "23505") {
      console.error("Mở visit lúc walk-in check-in lỗi:", vErr.message);
    }
  }

  return NextResponse.json({ ok: true, appointment_id: data.id });
}

type PatchAction =
  | "confirm"
  | "decline"
  | "complete"
  | "checkin"
  | "undo_checkin"
  | "cskh_confirm"
  | "cancel"
  | "no_show"
  | "reassign"
  | "reschedule";

interface PatchBody {
  id?: string;
  action?: PatchAction;
  cancellation_reason?: string; // cho action "cancel"
  doctor_id?: string; // "reassign"/"reschedule" (bác sĩ mới); rỗng = bỏ phân
  slot_start?: string; // cho action "reschedule" (ISO UTC)
  slot_end?: string; // cho action "reschedule" (ISO UTC)
}

// "complete" = bác sĩ chốt KHÁM XONG (lịch → COMPLETED). KHÔNG đụng visit
// (FINALIZED là khóa pháp lý riêng, không tự quyết ở đây).
const DOCTOR_ACTIONS = new Set<PatchAction>(["confirm", "decline", "complete"]);
// Front-desk (Lễ tân/CSKH/Quản lý) actions.
const CHECKIN_ACTIONS = new Set<PatchAction>([
  "checkin",
  "undo_checkin",
  "cskh_confirm",
]);
// Quản trị vòng đời lịch: hủy + phân lại + ĐỔI LỊCH (CSKH/Quản lý).
const MANAGE_ACTIONS = new Set<PatchAction>(["cancel", "reassign", "reschedule"]);
// no_show: front-desk đánh "không đến" (canCheckin).
const ALL_ACTIONS = new Set<PatchAction>([
  ...DOCTOR_ACTIONS,
  ...CHECKIN_ACTIONS,
  ...MANAGE_ACTIONS,
  "no_show",
]);

export async function PATCH(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  let body: PatchBody;
  try {
    body = (await request.json()) as PatchBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  const action = body.action;
  if (!id || !action || !ALL_ACTIONS.has(action)) {
    return NextResponse.json(
      { error: "Thiếu id lịch hẹn hoặc action không hợp lệ." },
      { status: 400 },
    );
  }

  const role = await getClinicRole();
  const staffId = await getClinicStaffId();

  // Gate theo nhóm: bác sĩ (own appt) · hủy/phân-lại (CSKH/QL) · không-đến
  // (front-desk) · check-in/cskh_confirm (intake).
  if (DOCTOR_ACTIONS.has(action)) {
    if (!isDoctorRole(role)) {
      return NextResponse.json(
        { error: "Chỉ bác sĩ mới xác nhận/từ chối/khám-xong lịch hẹn." },
        { status: 403 },
      );
    }
    if (!staffId) {
      return NextResponse.json(
        { error: "Chưa chọn danh tính bác sĩ." },
        { status: 403 },
      );
    }
  } else if (MANAGE_ACTIONS.has(action)) {
    if (!canManageAppt(role)) {
      return NextResponse.json(
        { error: "Chỉ CSKH / Quản lý mới hủy hoặc phân lại bác sĩ." },
        { status: 403 },
      );
    }
  } else if (action === "no_show") {
    if (!canCheckin(role)) {
      return NextResponse.json(
        { error: "Chỉ Lễ tân / Điều dưỡng / Quản lý mới đánh không đến." },
        { status: 403 },
      );
    }
  } else if (!canWriteIntake(role)) {
    return NextResponse.json(
      { error: "Chỉ Lễ tân / CSKH / Quản lý mới check-in bệnh nhân." },
      { status: 403 },
    );
  }

  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }

  const { data: appt, error: loadErr } = await db
    .from("appointment")
    .select("id, doctor_id, status, clinic_patient_id, slot_start, slot_end, queue_number, booking_channel")
    .eq("id", id)
    .maybeSingle();
  if (loadErr) {
    return NextResponse.json({ error: loadErr.message }, { status: 500 });
  }
  if (!appt) {
    return NextResponse.json({ error: "Không tìm thấy lịch hẹn." }, { status: 404 });
  }

  // Resolve the transition + the status it must currently be in (race guard).
  let newStatus: string;
  let fromStatuses: string[];
  if (action === "confirm" || action === "decline" || action === "complete") {
    if (appt.doctor_id !== staffId && role !== "TKYK") {
      return NextResponse.json(
        { error: "Lịch hẹn này không thuộc bác sĩ." },
        { status: 403 },
      );
    }
    if (action === "confirm") {
      // Bác sĩ NHẬN CA — kể cả lịch CSKH đã xác nhận với khách (2 bước).
      newStatus = "CONFIRMED";
      fromStatuses = ["SCHEDULED", "CSKH_CONFIRMED"];
    } else if (action === "decline") {
      // Bác sĩ TỪ CHỐI — từ lịch mới HOẶC lịch CSKH đã xác nhận → CSKH thấy "Đã huỷ".
      newStatus = "DOCTOR_DECLINED";
      fromStatuses = ["SCHEDULED", "CSKH_CONFIRMED"];
    } else {
      // Khám xong: BN PHẢI đã đến (lễ tân check-in) → COMPLETED. KHÔNG cho khám
      // xong khi mới CONFIRMED (bác sĩ nhận ca nhưng BN chưa tới quầy/chưa
      // check-in) — đúng vòng đời: …→CONFIRMED→CHECKED_IN→COMPLETED.
      newStatus = "COMPLETED";
      fromStatuses = ["CHECKED_IN"];
    }
  } else if (action === "checkin") {
    // D21 — BỎ HẲN bước "Bác sĩ duyệt": Lễ tân check-in THẲNG từ lịch còn sống
    // (SCHEDULED/CSKH_CONFIRMED/CONFIRMED), KHÔNG chờ bác sĩ nhận ca. BN đến →
    // check-in → khám được ngay. Đây là workflow appointment.status thuần —
    // KHÔNG đụng visit.status/FINALIZED/lab/043. (Nút "Nhận ca/Từ chối" của bác sĩ
    // vẫn còn để TỪ CHỐI → phân lại, nhưng KHÔNG còn là điều kiện để check-in.)
    newStatus = "CHECKED_IN";
    fromStatuses = ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"];
  } else if (action === "cskh_confirm") {
    // CSKH gọi xác nhận lịch với khách → SCHEDULED → CSKH_CONFIRMED. Lịch VẪN
    // chờ bác sĩ nhận ca (xác nhận 2 bước), nên vẫn nằm ở "Chờ xác nhận" của bác sĩ.
    newStatus = "CSKH_CONFIRMED";
    fromStatuses = ["SCHEDULED"];
  } else if (action === "cancel") {
    // Hủy lịch (CSKH/QL) — từ mọi trạng thái còn "sống".
    newStatus = "CANCELLED";
    fromStatuses = ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"];
  } else if (action === "no_show") {
    // Khách không đến (front-desk) — chỉ khi chưa check-in.
    newStatus = "NO_SHOW";
    fromStatuses = ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"];
  } else if (action === "reassign") {
    // Bác sĩ từ chối → CSKH/QL phân lại → về SCHEDULED (gán bác sĩ mới ở dưới).
    newStatus = "SCHEDULED";
    fromStatuses = ["DOCTOR_DECLINED"];
  } else if (action === "reschedule") {
    // Đổi lịch (CSKH/QL theo yêu cầu khách): GIỮ trạng thái, chỉ đổi giờ
    // (+ tuỳ chọn đổi bác sĩ). Chỉ đổi khi lịch còn "sống", chưa khám xong.
    newStatus = appt.status;
    fromStatuses = ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"];
  } else {
    // undo_checkin
    newStatus = "CONFIRMED";
    fromStatuses = ["CHECKED_IN"];
  }

  if (!fromStatuses.includes(appt.status)) {
    return NextResponse.json(
      { error: `Lịch hẹn đang ở trạng thái ${appt.status}, không thể thực hiện.` },
      { status: 409 },
    );
  }

  // Trường phụ theo action: hủy (ghi lý do + thời điểm), phân lại (gán bác sĩ mới).
  const patch: Record<string, unknown> = { status: newStatus };
  if (action === "cancel") {
    patch.cancelled_at = new Date().toISOString();
    patch.cancellation_reason = (body.cancellation_reason ?? "").trim() || null;
  } else if (action === "reassign") {
    const newDoctor = (body.doctor_id ?? "").trim() || null;
    patch.doctor_id = newDoctor;
    if (newDoctor) {
      const busy = await doctorConflictMessage(db, newDoctor, appt.slot_start, appt.slot_end, id);
      if (busy) return NextResponse.json({ error: busy }, { status: 409 });
    }
    // Luật 2+1: hàng đích (bác sĩ mới / "Chưa phân bác sĩ") phải còn chỗ đúng loại.
    const full = await slotCapMessage(
      db,
      newDoctor,
      appt.slot_start as string,
      (appt.booking_channel as string | null) ?? "",
      id,
    );
    if (full) return NextResponse.json({ error: full }, { status: 409 });
  } else if (action === "reschedule") {
    const ss = (body.slot_start ?? "").trim();
    const se = (body.slot_end ?? "").trim();
    if (!ss || !se) {
      return NextResponse.json({ error: "Thiếu giờ hẹn mới." }, { status: 400 });
    }
    if (new Date(se).getTime() <= new Date(ss).getTime()) {
      return NextResponse.json(
        { error: "Giờ kết thúc phải sau giờ bắt đầu." },
        { status: 400 },
      );
    }
    patch.slot_start = ss;
    patch.slot_end = se;
    // Chỉ đổi bác sĩ khi field doctor_id được gửi (rỗng = bỏ phân bác sĩ).
    if (body.doctor_id !== undefined) {
      patch.doctor_id = (body.doctor_id ?? "").trim() || null;
    }
    // Chặn TRÙNG GIỜ khi đổi lịch (báo rõ khung giờ bận) — loại trừ chính lịch này.
    const newDoctor = ("doctor_id" in patch
      ? patch.doctor_id
      : appt.doctor_id) as string | null;
    if (newDoctor) {
      const busy = await doctorConflictMessage(db, newDoctor, ss, se, id);
      if (busy) return NextResponse.json({ error: busy }, { status: 409 });
    }
    // Luật 2+1: khung giờ mới phải còn chỗ đúng loại (kể cả hàng chưa phân BS).
    const full = await slotCapMessage(
      db,
      newDoctor,
      ss,
      (appt.booking_channel as string | null) ?? "",
      id,
    );
    if (full) return NextResponse.json({ error: full }, { status: 409 });
  }

  // Check-in is special: status transition + daily queue allocation must be
  // one serialized DB transaction. All other transitions remain optimistic
  // updates guarded by their allowed source statuses.
  const updateResult =
    action === "checkin"
      ? await db.rpc("check_in_appointment", {
          p_appointment_id: id,
          p_from_statuses: fromStatuses,
        })
      : await db
          .from("appointment")
          .update(patch)
          .eq("id", id)
          .in("status", fromStatuses)
          .select("id");
  const { data: updated, error: updErr } = updateResult;
  if (updErr) {
    if (action === "checkin" && updErr.code === "42883") {
      return NextResponse.json(
        {
          error:
            "Chức năng cấp số an toàn chưa được cài đặt — cần chạy migration atomic queue check-in.",
        },
        { status: 503 },
      );
    }
    // 23P01 = exclusion_violation (bác sĩ trùng giờ) khi đổi lịch.
    if (updErr.code === "23P01") {
      return NextResponse.json(
        { error: "Bác sĩ đã có lịch trùng khung giờ mới này." },
        { status: 409 },
      );
    }
    // 23514 = check_violation. The atomic 2+1 slot-capacity trigger raises this
    // when a reschedule/reassign would overbook the target slot → clean 409.
    if (updErr.code === "23514" && /Khung giờ đã đầy/.test(updErr.message)) {
      return NextResponse.json({ error: updErr.message }, { status: 409 });
    }
    // Otherwise a 23514 most likely means the new status (CSKH_CONFIRMED) isn't
    // permitted by the DB → migration 041 (appointment_cskh_confirmed) not applied.
    if (updErr.code === "23514") {
      return NextResponse.json(
        {
          error:
            "Trạng thái lịch hẹn chưa được DB cho phép — cần chạy migration 041 (appointment_cskh_confirmed) trên Supabase.",
        },
        { status: 500 },
      );
    }
    return NextResponse.json({ error: updErr.message }, { status: 500 });
  }
  // Race: trạng thái đã bị người khác đổi giữa lúc đọc và ghi → 0 row khớp.
  if (!updated || updated.length === 0) {
    return NextResponse.json(
      { error: "Lịch hẹn vừa được người khác cập nhật, hãy tải lại." },
      { status: 409 },
    );
  }

  const eventType: Record<PatchAction, string> = {
    confirm: "appointment.confirmed",
    decline: "appointment.declined",
    complete: "appointment.completed",
    checkin: "appointment.checked_in",
    undo_checkin: "appointment.checkin_undone",
    cskh_confirm: "appointment.cskh_confirmed",
    cancel: "appointment.cancelled",
    no_show: "appointment.no_show",
    reassign: "appointment.reassigned",
    reschedule: "appointment.rescheduled",
  };

  await logEvent(db, {
    event_type: eventType[action],
    aggregate_type: "appointment",
    aggregate_id: id,
    payload: {
      appointment_id: id,
      status: newStatus,
      doctor_id: appt.doctor_id,
      clinic_patient_id: appt.clinic_patient_id,
      slot_start: appt.slot_start,
    },
    metadata: {
      clinic_role: role,
      clinic_staff_id: staffId,
      actor_auth_user_id: user.id,
      origin: `dashboard:appointment-${action}`,
    },
  });

  // Lễ tân check-in → MỞ lượt khám (visit OPEN) NGAY, để BN hiện trên bảng
  // "Trạng thái BN buổi khám hôm nay" (thanh tiến trình kiểu Grab) TỪ LÚC ĐẾN
  // QUẦY — không phải đợi bác sĩ/ĐD ghi hồ sơ mới hiện (lỗi BN báo: check-in xong
  // mà bảng trống). checked_in_at nuôi "đồng hồ chờ". UNIQUE(appointment_id)
  // (mig 039) → đã có visit thì bỏ qua (23505). clinical-record sau đó tìm thấy
  // visit OPEN này và ghi tiếp (OPEN ∈ WRITABLE) — KHÔNG tạo trùng. Best-effort:
  // lỗi / chưa có bảng visit KHÔNG chặn việc check-in (đã thành công ở trên).
  if (action === "checkin") {
    const { data: had } = await db
      .from("visit")
      .select("visit_id")
      .eq("appointment_id", id)
      .limit(1)
      .maybeSingle();
    if (!had) {
      const { error: vErr } = await db.from("visit").insert({
        clinic_patient_id: appt.clinic_patient_id,
        appointment_id: id,
        attending_doctor_id: appt.doctor_id ?? null,
        status: "OPEN",
        checked_in_at: new Date().toISOString(),
      });
      if (vErr && vErr.code !== "23505") {
        console.error("Mở visit lúc check-in lỗi:", vErr.message);
      }
    }
  }

  // reassign / reschedule ĐỔI bác sĩ → ĐỒNG BỘ attending_doctor_id của lượt khám
  // đang mở (OPEN/IN_PROGRESS) sang bác sĩ mới. Visit tạo lúc check-in copy
  // doctor_id CŨ; nếu không đồng bộ, hồ sơ + bảng "buổi khám hôm nay" ghi nhầm
  // bác sĩ cũ. Chỉ đụng visit CHƯA chốt. Best-effort (appointment đã cập nhật).
  if ((action === "reassign" || action === "reschedule") && "doctor_id" in patch) {
    const newDoctor = (patch.doctor_id as string | null) ?? null;
    const { error: vErr } = await db
      .from("visit")
      .update({ attending_doctor_id: newDoctor })
      .eq("appointment_id", id)
      .in("status", ["OPEN", "IN_PROGRESS"]);
    if (vErr)
      console.error(
        "Đồng bộ attending_doctor_id lúc reassign/reschedule lỗi:",
        vErr.message,
      );
  }

  // Hoàn tác check-in → gỡ lượt khám CHƯA bắt đầu (visit còn OPEN, chưa ghi gì)
  // để bảng trạng thái không còn BN ảo. CHỈ xoá khi status='OPEN' — đã sang
  // IN_PROGRESS/FINALIZED nghĩa là đã có dữ liệu lâm sàng → KHÔNG đụng. Best-effort.
  if (action === "undo_checkin") {
    const { error: delErr } = await db
      .from("visit")
      .delete()
      .eq("appointment_id", id)
      .eq("status", "OPEN");
    if (delErr) console.error("Gỡ visit OPEN lúc undo check-in lỗi:", delErr.message);
  }

  // CSKH xác nhận lịch → GHI THẬT 1 việc "Đặt hẹn" vào cskh_action ngay (không
  // chờ Zalo/Pancake). Hiện luôn ở board "Theo dõi tình trạng lịch hẹn" cột Đặt
  // hẹn. Upsert theo source_ref để không trùng khi xác nhận lại. Best-effort:
  // lỗi ghi log này KHÔNG làm hỏng việc xác nhận lịch (đã thành công ở trên).
  if (action === "cskh_confirm") {
    const slot = appt.slot_start ? new Date(appt.slot_start as string) : null;
    const slotStr = slot
      ? slot.toLocaleString("vi-VN", {
          timeZone: "Asia/Ho_Chi_Minh",
          day: "2-digit",
          month: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        })
      : "";
    const { error: caErr } = await db.from("cskh_action").upsert(
      {
        source_ref: `dash-confirm-${id}`,
        clinic_patient_id: appt.clinic_patient_id,
        category: "Đặt hẹn",
        status: "Đã xác nhận lịch hẹn",
        description: `CSKH xác nhận lịch hẹn${slotStr ? ` · ${slotStr}` : ""}`,
        source_created_at: new Date().toISOString(),
        created_by_text: "CSKH · dashboard",
        appointment_link_raw: id,
      },
      { onConflict: "source_ref" },
    );
    if (caErr) console.error("cskh_action upsert (confirm) lỗi:", caErr.message);
  }

  // CSKH ĐỔI LỊCH cho khách → ghi 1 việc "Đổi lịch" vào cskh_action (gom vào
  // cột "Đặt hẹn" của board theo dõi). Upsert theo source_ref để cập nhật khi
  // đổi nhiều lần. Best-effort.
  if (action === "reschedule") {
    const ns = (body.slot_start ?? "").trim();
    const nd = ns
      ? new Date(ns).toLocaleString("vi-VN", {
          timeZone: "Asia/Ho_Chi_Minh",
          day: "2-digit",
          month: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        })
      : "";
    const { error: caErr } = await db.from("cskh_action").upsert(
      {
        source_ref: `dash-resched-${id}`,
        clinic_patient_id: appt.clinic_patient_id,
        category: "Đổi lịch",
        status: "Đã đổi lịch hẹn",
        description: `CSKH đổi lịch hẹn${nd ? ` · giờ mới ${nd}` : ""}`,
        source_created_at: new Date().toISOString(),
        created_by_text: "CSKH · dashboard",
        appointment_link_raw: id,
      },
      { onConflict: "source_ref" },
    );
    if (caErr) console.error("cskh_action upsert (reschedule) lỗi:", caErr.message);
  }

  // Bác sĩ "Khám xong" → ghi việc "CSKH sau khám" để CSKH chăm sóc sau khám
  // (cột đó trước đây luôn rỗng vì chưa nối Zalo).
  if (action === "complete") {
    const { error: caErr } = await db.from("cskh_action").upsert(
      {
        source_ref: `dash-postvisit-${id}`,
        clinic_patient_id: appt.clinic_patient_id,
        category: "CSKH sau khám",
        status: "Đã khám xong",
        description: "Bệnh nhân đã khám xong — chăm sóc/nhắc tái khám.",
        source_created_at: new Date().toISOString(),
        created_by_text: "Bác sĩ · dashboard",
        appointment_link_raw: id,
      },
      { onConflict: "source_ref" },
    );
    if (caErr) console.error("cskh_action upsert (complete) lỗi:", caErr.message);

    // MỐC "Khám xong" → lưu THỜI ĐIỂM vào visit.exam_completed_at (mig 058) phục vụ
    // phân tích thời gian khám (= exam_completed_at − checked_in_at). Tìm visit theo
    // appointment_id, chỉ set khi CHƯA có (giữ mốc lần khám-xong đầu tiên). Best-effort:
    // cột chưa migrate (42703) / chưa có visit → bỏ qua, KHÔNG làm hỏng việc khám-xong.
    try {
      const { error: exErr } = await db
        .from("visit")
        .update({ exam_completed_at: new Date().toISOString() })
        .eq("appointment_id", id)
        .is("exam_completed_at", null);
      if (exErr && exErr.code !== "42703") {
        console.error("visit.exam_completed_at stamp lỗi:", exErr.message);
      }
    } catch (e) {
      console.error("visit.exam_completed_at stamp lỗi:", e);
    }

    // Đợt khám (T-20260629-EPI-01) — BS khám xong mà KHÔNG hẹn lần sau (không còn lịch
    // tương lai cùng dịch vụ) → đặt đợt sang PENDING_CLOSE chờ CSKH xác nhận đóng. Chỉ
    // chuyển từ OPEN. Best-effort: lỗi / bảng chưa migrate → bỏ qua, không hỏng khám-xong.
    try {
      const { data: ap } = await db
        .from("appointment")
        .select("episode_id, service_type_id, clinic_patient_id")
        .eq("id", id)
        .maybeSingle();
      const apx = ap as {
        episode_id: string | null;
        service_type_id: string;
        clinic_patient_id: string;
      } | null;
      if (apx?.episode_id) {
        const nowIso = new Date().toISOString();
        const { count: future } = await db
          .from("appointment")
          .select("id", { count: "exact", head: true })
          .eq("clinic_patient_id", apx.clinic_patient_id)
          .eq("service_type_id", apx.service_type_id)
          .gt("slot_start", nowIso)
          .not("status", "in", "(CANCELLED,NO_SHOW,DOCTOR_DECLINED)");
        if (!future || future === 0) {
          await db
            .from("care_episode")
            .update({ status: "PENDING_CLOSE", last_visit_at: nowIso, updated_at: nowIso })
            .eq("id", apx.episode_id)
            .eq("status", "OPEN");
        }
      }
    } catch (e) {
      console.error("episode pending-close lỗi:", e);
    }
  }

  // Bác sĩ NHẬN CA (confirm) → TỰ THÊM lịch bác sĩ vào "Lịch làm việc" (work_roster)
  // cột "Lịch khám" của ĐÚNG ngày hẹn: bác sĩ có khám hôm đó → hiện trên bảng Lịch
  // làm việc tuần. Chống trùng (1 bác sĩ / 1 ngày chỉ 1 dòng "Lịch khám"). Best-effort.
  if (action === "confirm" && staffId && appt.slot_start) {
    try {
      const workDate = new Date(
        new Date(appt.slot_start as string).getTime() + 7 * 3_600_000,
      )
        .toISOString()
        .slice(0, 10); // ngày theo lịch VN
      const { data: existing } = await db
        .from("work_roster")
        .select("id")
        .eq("work_date", workDate)
        .eq("station", "LICH_KHAM")
        .eq("staff_id", staffId)
        .limit(1);
      if (!existing || existing.length === 0) {
        const { data: doc } = await db
          .from("staff")
          .select("full_name")
          .eq("id", staffId)
          .maybeSingle();
        const { error: wrErr } = await db.from("work_roster").insert({
          week_start: weekStartOf(workDate),
          work_date: workDate,
          shift: "FULL",
          station: "LICH_KHAM",
          staff_id: staffId,
          staff_name: (doc?.full_name as string | undefined) ?? "Bác sĩ",
        });
        if (wrErr) console.error("work_roster auto-insert lỗi:", wrErr.message);
      }
    } catch (e) {
      console.error("work_roster auto-insert (confirm) lỗi:", e);
    }
  }

  return NextResponse.json({ ok: true, status: newStatus });
}
