// CSKH bấm "Đã gọi" cho BN quá hạn tái khám → ghi 1 dòng NHẬT KÝ CSKH (cskh_log).
// TÁI DÙNG cột cskh_followup/cskh_status đã có (mig 037) — KHÔNG migration.
// cskh_log chỉ có RLS SELECT → ghi qua service-role. Gate = intake role (CSKH/QL/…).
//
//   POST { clinic_patient_id, note? } → { ok: true, id } | 4xx.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole } from "../../../lib/clinic-session";
import { canWriteIntake } from "../../../lib/roles";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";

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

  // FastAPI owns the write and stamps the working day in Asia/Ho_Chi_Minh,
  // for the same reason this route did.
  return proxyJsonToBackend("POST", "/api/v1/cskh/followup-calls", {
    clinic_patient_id: clinicPatientId,
    note,
  });
}
