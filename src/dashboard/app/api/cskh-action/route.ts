// CSKH ghi TAY 1 việc chăm sóc khách (feedback B4) — bổ sung cho phần tự-ghi
// (xác nhận lịch / khám xong). Bảng cskh_action chỉ có RLS SELECT → ghi qua
// service-role. Gate = shared session + intake role (CSKH/Lễ tân/Điều dưỡng/QL).
//
//   POST { category, description, status?, patient_code? }
//     → { ok: true, id }    | 404 nếu patient_code không khớp BN nào.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole } from "../../../lib/clinic-session";
import { canWriteIntake } from "../../../lib/roles";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";

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

  // The patient lookup, the insert and its audit event share one transaction
  // in FastAPI.
  return proxyJsonToBackend("POST", "/api/v1/cskh/actions", {
    category,
    description,
    status,
    patient_code: patientCode || null,
  });
}
