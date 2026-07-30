// /api/lab-result — luồng Xét nghiệm (XN chủ yếu gửi lab ngoài, kết quả PDF).
//   POST  { clinicPatientId, appointmentId?, test_name }           (BÁC SĨ)
//         → chỉ định XN: tạo lab_result triage_group='PENDING' (chờ kết quả).
//   PATCH { lab_result_id, result_value?, result_link?, lab_provider? }  (ĐD/Lễ tân/QL)
//         → đính tóm tắt + LINK phiếu PDF + nhà cung cấp lab.
// Ghi qua service-role (lab_result chỉ có RLS SELECT). Link PDF lưu ở external_ref
// (v1 dán link; upload Storage = v2). KHÔNG tự finalize (is_finalized = safety gate).

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getSupabaseService } from "../../../lib/supabase-service";
import { getClinicRole, getClinicStaffId } from "../../../lib/clinic-session";
import { isDoctorRole, canWriteClinical } from "../../../lib/roles";
import { logEvent } from "../../../lib/event-log";
import { toHref } from "../../../lib/url";
import { labViaBackend, proxyJsonToBackend } from "../../../lib/backend-proxy";

interface PostBody {
  clinicPatientId?: string;
  appointmentId?: string;
  test_name?: string;
}
interface PatchBody {
  lab_result_id?: string;
  result_value?: string;
  result_link?: string;
  lab_provider?: string;
}

export async function POST(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const role = await getClinicRole();
  if (!isDoctorRole(role)) {
    return NextResponse.json(
      { error: "Chỉ bác sĩ mới chỉ định xét nghiệm." },
      { status: 403 },
    );
  }
  const staffId = await getClinicStaffId();

  let body: PostBody;
  try {
    body = (await request.json()) as PostBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const clinicPatientId = (body.clinicPatientId ?? "").trim();
  const testName = (body.test_name ?? "").trim();
  const appointmentId = (body.appointmentId ?? "").trim() || null;
  if (!clinicPatientId || !testName) {
    return NextResponse.json(
      { error: "Thiếu bệnh nhân hoặc tên xét nghiệm." },
      { status: 400 },
    );
  }

  // W5 (ADR-0012): the rule lives in FastAPI, where the insert and its audit
  // event share a transaction. Off until LAB_VIA_BACKEND=1; this branch and the
  // service-role client below are what get deleted once the flag is permanent.
  if (labViaBackend()) {
    return proxyJsonToBackend("POST", "/api/v1/lab/orders", {
      clinic_patient_id: clinicPatientId,
      test_name: testName,
      appointment_id: appointmentId,
    });
  }

  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }

  const { data, error } = await db
    .from("lab_result")
    .insert({
      clinic_patient_id: clinicPatientId,
      appointment_id: appointmentId,
      test_code: "MANUAL",
      test_name: testName,
      triage_group: "PENDING",
    })
    .select("lab_result_id")
    .single();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  await logEvent(db, {
    event_type: "lab_result.ordered",
    aggregate_type: "lab_result",
    aggregate_id: data.lab_result_id,
    payload: { lab_result_id: data.lab_result_id, clinic_patient_id: clinicPatientId, test_name: testName },
    metadata: { clinic_role: role, clinic_staff_id: staffId, actor_auth_user_id: user.id, origin: "dashboard:lab-order" },
  });

  return NextResponse.json({ ok: true, lab_result_id: data.lab_result_id });
}

export async function PATCH(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const role = await getClinicRole();
  // KQ xét nghiệm = LÂM SÀNG → chỉ Bác sĩ / Điều dưỡng / Thư ký Y khoa.
  // Lễ tân / Quản lý KHÔNG nhập (recap 17/6).
  if (!canWriteClinical(role)) {
    return NextResponse.json(
      { error: "Chỉ Bác sĩ / Điều dưỡng / Thư ký Y khoa mới nhập kết quả XN." },
      { status: 403 },
    );
  }
  const staffId = await getClinicStaffId();

  let body: PatchBody;
  try {
    body = (await request.json()) as PatchBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.lab_result_id ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id kết quả." }, { status: 400 });

  const resultValue = (body.result_value ?? "").trim() || null;
  // Chuẩn hoá link: thêm https:// nếu thiếu scheme (tránh 404 do mở như đường dẫn nội bộ).
  const resultLink = toHref(body.result_link);
  const labProvider = (body.lab_provider ?? "").trim() || null;
  if (!resultValue && !resultLink) {
    return NextResponse.json(
      { error: "Nhập tóm tắt kết quả hoặc dán link phiếu." },
      { status: 400 },
    );
  }

  if (labViaBackend()) {
    return proxyJsonToBackend("PATCH", `/api/v1/lab/results/${id}`, {
      result_value: resultValue,
      result_link: resultLink,
      lab_provider: labProvider,
    });
  }

  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }

  const { data, error } = await db
    .from("lab_result")
    .update({
      result_value: resultValue,
      external_ref: resultLink,
      lab_provider: labProvider,
      result_received_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
    .eq("lab_result_id", id)
    .select("lab_result_id")
    .maybeSingle();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!data) {
    return NextResponse.json({ error: "Không tìm thấy kết quả XN." }, { status: 404 });
  }

  await logEvent(db, {
    event_type: "lab_result.entered",
    aggregate_type: "lab_result",
    aggregate_id: id,
    payload: { lab_result_id: id, has_link: !!resultLink },
    metadata: { clinic_role: role, clinic_staff_id: staffId, actor_auth_user_id: user.id, origin: "dashboard:lab-entry" },
  });

  return NextResponse.json({ ok: true });
}
