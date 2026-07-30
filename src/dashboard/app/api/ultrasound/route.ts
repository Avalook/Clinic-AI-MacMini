// /api/ultrasound — SỐ ĐO SIÊU ÂM THAI gắn vào visit (ultrasound_record.findings JSONB).
//   GET  ?appointmentId=  → { record: { findings, performed_at } | null }
//   POST { appointmentId, clinicPatientId, measurements?, is_abnormal?, status? }
//        → find-or-create visit (BS siêu âm tự khám) → upsert ultrasound_record.
//
// 7 số đo chuẩn: CRL/NT/BPD/HC/AC/FL (mm) + EFW (gram). EFW NHẬP TAY — KHÔNG tự tính
// (Hadlock…) vì chưa BS Thắng xác nhận công thức (xem // TODO auto-EFW dưới).
// Gate: CHỈ Bác sĩ Siêu âm (ULTRASOUND_DOCTOR) — KHÔNG mở rộng. KHÔNG đụng
// visit.status FINALIZED (chỉ ghi vào visit OPEN/IN_PROGRESS), KHÔNG suy luận bất
// thường (cờ do BS bấm tay).

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getSupabaseService } from "../../../lib/supabase-service";
import { getClinicRole, getClinicStaffId } from "../../../lib/clinic-session";
import { isUltrasoundDoctorRole } from "../../../lib/roles";
import {
  proxyJsonToBackend,
  ultrasoundViaBackend,
} from "../../../lib/backend-proxy";

const MEASURE_KEYS = ["crl", "nt", "bpd", "hc", "ac", "fl", "efw"] as const;
const WRITABLE_VISIT_STATUSES = ["OPEN", "IN_PROGRESS"];

interface UltrasoundFindings {
  crl?: number | null;
  nt?: number | null;
  bpd?: number | null;
  hc?: number | null;
  ac?: number | null;
  fl?: number | null;
  efw?: number | null; // TODO auto-EFW: tự tính từ BPD/HC/AC/FL khi BS Thắng chốt công thức.
  is_abnormal?: boolean;
  status?: "in_progress" | "completed";
}

function numOrNull(v: unknown): number | null {
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export async function GET(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  if (!isUltrasoundDoctorRole(await getClinicRole())) {
    return NextResponse.json({ error: "Chỉ Bác sĩ Siêu âm." }, { status: 403 });
  }

  const appointmentId = new URL(request.url).searchParams
    .get("appointmentId")
    ?.trim();
  if (!appointmentId) return NextResponse.json({ record: null });

  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }
  const { data: visit } = await db
    .from("visit")
    .select("visit_id")
    .eq("appointment_id", appointmentId)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (!visit) return NextResponse.json({ record: null });

  const { data: rec } = await db
    .from("ultrasound_record")
    .select("ultrasound_id, findings, performed_at")
    .eq("visit_id", visit.visit_id)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  return NextResponse.json({ record: rec ?? null });
}

interface PostBody {
  appointmentId?: string;
  clinicPatientId?: string;
  measurements?: Record<string, unknown>;
  is_abnormal?: boolean;
  status?: "in_progress" | "completed";
}

export async function POST(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const role = await getClinicRole();
  if (!isUltrasoundDoctorRole(role)) {
    return NextResponse.json({ error: "Chỉ Bác sĩ Siêu âm." }, { status: 403 });
  }
  const staffId = await getClinicStaffId();

  let body: PostBody;
  try {
    body = (await request.json()) as PostBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const appointmentId = (body.appointmentId ?? "").trim();
  const clinicPatientId = (body.clinicPatientId ?? "").trim();
  if (!appointmentId || !clinicPatientId) {
    return NextResponse.json(
      { error: "Thiếu lịch hẹn hoặc bệnh nhân." },
      { status: 400 },
    );
  }

  // W5 (ADR-0012): the rule lives in FastAPI, where find-or-create visit and the
  // record write share a transaction — here they did not, so a crash between
  // them left an empty visit on the appointment. Off until
  // ULTRASOUND_VIA_BACKEND=1.
  if (ultrasoundViaBackend()) {
    return proxyJsonToBackend("POST", "/api/v1/ultrasound/measurements", {
      appointment_id: appointmentId,
      clinic_patient_id: clinicPatientId,
      measurements: body.measurements ?? null,
      is_abnormal: body.is_abnormal ?? null,
      status: body.status ?? null,
    });
  }

  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }

  // find-or-create visit (BS siêu âm tự khám → attending = chính mình).
  const { data: existingVisit } = await db
    .from("visit")
    .select("visit_id, status")
    .eq("appointment_id", appointmentId)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  let visitId = existingVisit?.visit_id ?? null;
  if (existingVisit && !WRITABLE_VISIT_STATUSES.includes(existingVisit.status)) {
    return NextResponse.json(
      { error: `Hồ sơ đã chốt (${existingVisit.status}) — không sửa số đo.` },
      { status: 409 },
    );
  }
  if (!visitId) {
    const { data: created, error: vErr } = await db
      .from("visit")
      .insert({
        clinic_patient_id: clinicPatientId,
        appointment_id: appointmentId,
        attending_doctor_id: staffId,
        status: "IN_PROGRESS",
        checked_in_at: new Date().toISOString(),
      })
      .select("visit_id")
      .single();
    if (vErr || !created) {
      return NextResponse.json(
        { error: vErr?.message ?? "Không tạo được lượt khám." },
        { status: 500 },
      );
    }
    visitId = created.visit_id;
  }

  // upsert 1 ultrasound_record / visit. Merge số đo vào findings JSONB.
  const { data: rec } = await db
    .from("ultrasound_record")
    .select("ultrasound_id, findings")
    .eq("visit_id", visitId)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  const prev = (rec?.findings as UltrasoundFindings | null) ?? {};
  const next: UltrasoundFindings = { ...prev };
  if (body.measurements) {
    for (const k of MEASURE_KEYS) next[k] = numOrNull(body.measurements[k]);
  }
  if (typeof body.is_abnormal === "boolean") next.is_abnormal = body.is_abnormal;
  if (body.status) next.status = body.status;

  const nowIso = new Date().toISOString();
  if (rec) {
    const { error } = await db
      .from("ultrasound_record")
      .update({ findings: next, performed_by: staffId, performed_at: nowIso })
      .eq("ultrasound_id", rec.ultrasound_id);
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  } else {
    const { error } = await db.from("ultrasound_record").insert({
      visit_id: visitId,
      clinic_patient_id: clinicPatientId,
      performed_by: staffId,
      ultrasound_type: "Thai",
      findings: next,
      performed_at: nowIso,
    });
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  }
  return NextResponse.json({ ok: true, findings: next });
}
