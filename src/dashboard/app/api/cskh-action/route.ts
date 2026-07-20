// CSKH ghi TAY 1 việc chăm sóc khách (feedback B4) — bổ sung cho phần tự-ghi
// (xác nhận lịch / khám xong). Bảng cskh_action chỉ có RLS SELECT → ghi qua
// service-role. Gate = shared session + intake role (CSKH/Lễ tân/Điều dưỡng/QL).
//
//   POST { category, description, status?, patient_code? }
//     → { ok: true, id }    | 404 nếu patient_code không khớp BN nào.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getSupabaseService } from "../../../lib/supabase-service";
import { getClinicRole, getClinicStaffId } from "../../../lib/clinic-session";
import { canWriteIntake } from "../../../lib/roles";
import { logEvent } from "../../../lib/event-log";

interface Body {
  category?: string;
  description?: string;
  status?: string;
  patient_code?: string;
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

  const category = (body.category ?? "").trim();
  const description = (body.description ?? "").trim();
  const status = (body.status ?? "").trim() || null;
  const patientCode = (body.patient_code ?? "").trim();
  if (!category) {
    return NextResponse.json({ error: "Thiếu loại việc." }, { status: 400 });
  }
  if (!description) {
    return NextResponse.json({ error: "Phải nhập nội dung việc." }, { status: 400 });
  }

  // Mã BN tuỳ chọn → resolve sang clinic_patient_id (để gắn việc vào hồ sơ).
  let clinicPatientId: string | null = null;
  if (patientCode) {
    const { data: p } = await db
      .from("patient")
      .select("clinic_patient_id")
      .eq("patient_code", patientCode)
      .maybeSingle();
    clinicPatientId = (p?.clinic_patient_id as string | null) ?? null;
    if (!clinicPatientId) {
      return NextResponse.json(
        { error: `Không tìm thấy bệnh nhân mã ${patientCode}.` },
        { status: 404 },
      );
    }
  }

  // source_ref UNIQUE NOT NULL → sinh mã duy nhất cho việc nhập tay.
  const sourceRef = `dash-manual-${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
  const { data, error } = await db
    .from("cskh_action")
    .insert({
      source_ref: sourceRef,
      clinic_patient_id: clinicPatientId,
      category,
      status,
      description,
      source_created_at: new Date().toISOString(),
      created_by_text: "CSKH · dashboard",
      patient_link_raw: patientCode || null,
    })
    .select("id")
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  await logEvent(db, {
    event_type: "cskh_action.created",
    aggregate_type: "cskh_action",
    aggregate_id: data.id,
    payload: { id: data.id, category, status, clinic_patient_id: clinicPatientId },
    metadata: {
      clinic_role: role,
      clinic_staff_id: staffId,
      actor_auth_user_id: user.id,
      origin: "dashboard:cskh-action-manual",
    },
  });

  return NextResponse.json({ ok: true, id: data.id });
}
