// CSKH bấm "Đã gọi" cho BN quá hạn tái khám → ghi 1 dòng NHẬT KÝ CSKH (cskh_log).
// TÁI DÙNG cột cskh_followup/cskh_status đã có (mig 037) — KHÔNG migration.
// cskh_log chỉ có RLS SELECT → ghi qua service-role. Gate = intake role (CSKH/QL/…).
//
//   POST { clinic_patient_id, note? } → { ok: true, id } | 4xx.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getSupabaseService } from "../../../lib/supabase-service";
import { getClinicRole, getClinicStaffId } from "../../../lib/clinic-session";
import { canWriteIntake } from "../../../lib/roles";
import { logEvent } from "../../../lib/event-log";
import { cskhViaBackend, proxyJsonToBackend } from "../../../lib/backend-proxy";

interface Body {
  clinic_patient_id?: string;
  note?: string;
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

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const clinicPatientId = (body.clinic_patient_id ?? "").trim();
  if (!clinicPatientId) {
    return NextResponse.json({ error: "Thiếu clinic_patient_id." }, { status: 400 });
  }
  const note = (body.note ?? "").trim() || null;

  // W5 (ADR-0012): FastAPI owns the write and stamps the working day in
  // Asia/Ho_Chi_Minh, for the same reason this route did.
  if (cskhViaBackend()) {
    return proxyJsonToBackend("POST", "/api/v1/cskh/followup-calls", {
      clinic_patient_id: clinicPatientId,
      note,
    });
  }

  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }

  const todayVn = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Ho_Chi_Minh" });

  const { data, error } = await db
    .from("cskh_log")
    .insert({
      clinic_patient_id: clinicPatientId,
      work_date: todayVn,
      cskh_status: "Đã gọi nhắc tái khám",
      cskh_followup: "Nhắc gọi tái khám",
      last_cskh_date: todayVn,
      cskh_by: "CSKH · dashboard",
      note,
    })
    .select("id")
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  await logEvent(db, {
    event_type: "cskh_log.followup_call",
    aggregate_type: "cskh_log",
    aggregate_id: data.id,
    payload: { id: data.id, clinic_patient_id: clinicPatientId, kind: "nhac_goi" },
    metadata: {
      clinic_role: role,
      clinic_staff_id: staffId,
      actor_auth_user_id: user.id,
      origin: "dashboard:cskh-followup",
    },
  });

  return NextResponse.json({ ok: true, id: data.id });
}
