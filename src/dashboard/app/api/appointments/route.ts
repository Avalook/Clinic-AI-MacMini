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
import { getClinicRole, getClinicStaffId } from "../../../lib/clinic-session";
import {
  canWriteIntake,
  isDoctorRole,
  canManageAppt,
  canCheckin,
} from "../../../lib/roles";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";
import {
  suggestLoad,
  type PatientKind,
} from "../../../lib/capacity";

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

  let query = caller
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
  // Booking, the 2+1 pre-check, the episode attach, the audit events and the
  // walk-in auto-check-in all run in ONE transaction in FastAPI. Here they were
  // six sequential calls, so a crash mid-way left half a booking behind.
  return proxyJsonToBackend("POST", "/api/v1/appointments/bookings", {
    clinic_patient_id,
    service_type_id,
    location_id,
    slot_start,
    slot_end,
    doctor_id,
    booking_channel: rawChannel || null,
    queue_number,
    patient_kind,
    need_sono,
    thanh_min,
    sono_min,
  });
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

  return proxyJsonToBackend("PATCH", `/api/v1/appointments/${id}`, {
    action,
    cancellation_reason: body.cancellation_reason ?? null,
    ...(body.doctor_id !== undefined ? { doctor_id: body.doctor_id || null } : {}),
    slot_start: body.slot_start ?? null,
    slot_end: body.slot_end ?? null,
  });
}
