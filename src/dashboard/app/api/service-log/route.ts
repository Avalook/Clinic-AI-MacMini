// /api/service-log — luồng Dịch vụ / thủ thuật (điều dưỡng/KTV thực hiện).
//   POST  { service_name, patient_code?, performer? }   → tạo việc (chờ làm).
//   PATCH { id, action: "start" | "finish", result_text? }
//         start  → started_at = now, status 'Đang làm'.
//         finish → finished_at = now, status 'Hoàn tất' (+ result_text).
// Ghi qua service-role (service_log chỉ có RLS SELECT). Gate = canCheckin
// (ĐD/Lễ tân/QL).

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getSupabaseService } from "../../../lib/supabase-service";
import { proxyJsonToBackend, serviceLogViaBackend } from "../../../lib/backend-proxy";
import { getClinicRole, getClinicStaffId } from "../../../lib/clinic-session";
import { canWriteClinical } from "../../../lib/roles";
import { logEvent } from "../../../lib/event-log";

interface PostBody {
  service_name?: string;
  patient_code?: string;
  performer?: string;
}
interface PatchBody {
  id?: string;
  action?: "start" | "finish";
  result_text?: string;
}

async function guard() {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) {
    return { res: NextResponse.json({ error: "Unauthorised" }, { status: 401 }) };
  }
  const role = await getClinicRole();
  // Log dịch vụ (SA/XN) = LÂM SÀNG → chỉ Bác sĩ / Điều dưỡng / Thư ký Y khoa.
  // Lễ tân / Quản lý KHÔNG ghi (recap 17/6).
  if (!canWriteClinical(role)) {
    return {
      res: NextResponse.json(
        { error: "Chỉ Bác sĩ / Điều dưỡng / Thư ký Y khoa mới ghi dịch vụ." },
        { status: 403 },
      ),
    };
  }
  const db = getSupabaseService();
  if (!db) {
    return {
      res: NextResponse.json(
        { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
        { status: 503 },
      ),
    };
  }
  return { user, role, db };
}

export async function POST(request: Request) {
  const g = await guard();
  if ("res" in g) return g.res;
  const { user, role, db } = g;
  const staffId = await getClinicStaffId();

  let body: PostBody;
  try {
    body = (await request.json()) as PostBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const serviceName = (body.service_name ?? "").trim();
  const patientCode = (body.patient_code ?? "").trim();
  const performer = (body.performer ?? "").trim() || null;
  if (!serviceName) {
    return NextResponse.json({ error: "Thiếu tên dịch vụ." }, { status: 400 });
  }

  // W5 (ADR-0012): patient lookup, insert and audit event share one transaction
  // in FastAPI. Off until SERVICE_LOG_VIA_BACKEND=1.
  if (serviceLogViaBackend()) {
    return proxyJsonToBackend("POST", "/api/v1/service-log", {
      service_name: serviceName,
      patient_code: patientCode || null,
      performer,
    });
  }

  // Mã BN tuỳ chọn → resolve clinic_patient_id.
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

  const sourceRef = `dash-svc-${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
  const { data, error } = await db
    .from("service_log")
    .insert({
      source_ref: sourceRef,
      clinic_patient_id: clinicPatientId,
      service_name_raw: serviceName,
      performer_text: performer,
      status: "Chờ làm",
      ordered_at: new Date().toISOString(),
      created_by_text: `${role} · dashboard`,
      patient_link_raw: patientCode || null,
    })
    .select("id")
    .single();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  await logEvent(db, {
    event_type: "service_log.created",
    aggregate_type: "service_log",
    aggregate_id: data.id,
    payload: { id: data.id, service_name: serviceName, clinic_patient_id: clinicPatientId },
    metadata: { clinic_role: role, clinic_staff_id: staffId, actor_auth_user_id: user.id, origin: "dashboard:service-create" },
  });

  return NextResponse.json({ ok: true, id: data.id });
}

export async function PATCH(request: Request) {
  const g = await guard();
  if ("res" in g) return g.res;
  const { user, role, db } = g;
  const staffId = await getClinicStaffId();

  let body: PatchBody;
  try {
    body = (await request.json()) as PatchBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  const action = body.action;
  if (!id || (action !== "start" && action !== "finish")) {
    return NextResponse.json({ error: "Thiếu id hoặc action không hợp lệ." }, { status: 400 });
  }

  if (serviceLogViaBackend()) {
    return proxyJsonToBackend("PATCH", `/api/v1/service-log/${id}`, {
      action,
      result_text: body.result_text ?? null,
    });
  }

  const now = new Date().toISOString();
  const patch: Record<string, unknown> = { updated_at: now };
  if (action === "start") {
    patch.started_at = now;
    patch.status = "Đang làm";
  } else {
    patch.finished_at = now;
    patch.status = "Hoàn tất";
    patch.result_text = (body.result_text ?? "").trim() || null;
  }

  const { data, error } = await db
    .from("service_log")
    .update(patch)
    .eq("id", id)
    .select("id")
    .maybeSingle();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!data) return NextResponse.json({ error: "Không tìm thấy dịch vụ." }, { status: 404 });

  await logEvent(db, {
    event_type: `service_log.${action === "start" ? "started" : "finished"}`,
    aggregate_type: "service_log",
    aggregate_id: id,
    payload: { id, action },
    metadata: { clinic_role: role, clinic_staff_id: staffId, actor_auth_user_id: user.id, origin: `dashboard:service-${action}` },
  });

  return NextResponse.json({ ok: true });
}
