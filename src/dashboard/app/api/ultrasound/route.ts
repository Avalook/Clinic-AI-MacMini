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
import { getClinicRole } from "../../../lib/clinic-session";
import { isUltrasoundDoctorRole } from "../../../lib/roles";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";


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

  const { data: visit } = await caller
    .from("visit")
    .select("visit_id")
    .eq("appointment_id", appointmentId)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (!visit) return NextResponse.json({ record: null });

  const { data: rec } = await caller
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

  // FastAPI owns this: find-or-create visit and the record write share a
  // transaction there. Here they did not, so a crash between them left an empty
  // visit on the appointment.
  return proxyJsonToBackend("POST", "/api/v1/ultrasound/measurements", {
    appointment_id: appointmentId,
    clinic_patient_id: clinicPatientId,
    measurements: body.measurements ?? null,
  });
}
