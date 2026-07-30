// /api/clinical-record
//   GET  ?patientId=&appointmentId=  → data đồng bộ (tiền sử/thai/XN) + bản NHÁP
//        hồ sơ khám của lịch này (để prefill phần bác sĩ điền).
//   POST { appointmentId, clinicPatientId, draft } → LƯU NHÁP hồ sơ khám.
//
// AN TOÀN (TT13/2011/TT-BYT): chỉ ghi vào visit OPEN/IN_PROGRESS; nếu visit đã
// FINALIZED → 409 (luật cấm sửa, phải đính chính). KHÔNG bao giờ tự set FINALIZED.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";
import { getClinicRole } from "../../../lib/clinic-session";
import { isDoctorRole, isNurseRole, isThuKyRole } from "../../../lib/roles";

interface ClinicalRecordRow {
  chief_complaint_at_visit: string | null;
  soap_subjective: unknown;
  soap_objective: unknown;
  soap_assessment: unknown;
  soap_plan: unknown;
}
interface VisitRow {
  visit_id: string;
  status: string;
  created_at: string | null;
  clinical_record: ClinicalRecordRow | ClinicalRecordRow[] | null;
}

interface HistoryVisitRow {
  visit_id: string;
  status: string;
  created_at: string;
  appointment_id: string | null;
  service: { name: string } | { name: string }[] | null;
  doctor: { full_name: string } | { full_name: string }[] | null;
  clinical_record:
    | { chief_complaint_at_visit: string | null; soap_assessment: unknown }
    | { chief_complaint_at_visit: string | null; soap_assessment: unknown }[]
    | null;
}

/** JSONB SOAP có thể là chuỗi hoặc object → gộp thành text đọc được. */
function flatten(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "string") return v.trim();
  if (typeof v === "object") {
    return Object.values(v as Record<string, unknown>)
      .filter((x): x is string => typeof x === "string" && x.trim() !== "")
      .map((x) => x.trim())
      .join(" · ");
  }
  return String(v);
}

function one<T>(x: T | T[] | null): T | null {
  if (!x) return null;
  return Array.isArray(x) ? (x[0] ?? null) : x;
}

export async function GET(request: Request) {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const url = new URL(request.url);
  const patientId = url.searchParams.get("patientId");
  const appointmentId = url.searchParams.get("appointmentId");
  // visitId = xem 1 LƯỢT KHÁM cũ cụ thể (pager ◀▶ trong phiếu khám, chỉ đọc).
  // Khi có visitId → nạp đúng visit đó (draft + đơn thuốc); appointmentId bỏ qua.
  const visitId = url.searchParams.get("visitId");
  if (!patientId) {
    return NextResponse.json({ error: "Thiếu patientId." }, { status: 400 });
  }

  const [profileRes, pregRes, labRes, visitRes, historyRes] = await Promise.all([
    supabase
      .from("patient_medical_profile")
      .select(
        "blood_type, allergies, chronic_diseases, current_medications, surgical_history, family_history, notes",
      )
      .eq("clinic_patient_id", patientId)
      .maybeSingle(),
    supabase
      .from("pregnancy")
      .select("edd_date, gestational_age_at_registration, is_high_risk, high_risk_reason, outcome")
      .eq("clinic_patient_id", patientId)
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle(),
    supabase
      .from("lab_result")
      .select(
        "test_name, result_value, result_numeric, result_unit, flag, external_ref, triage_group, result_received_at",
      )
      .eq("clinic_patient_id", patientId)
      .order("result_received_at", { ascending: false })
      .limit(20),
    visitId
      ? supabase
          .from("visit")
          .select(
            "visit_id, status, created_at, clinical_record ( chief_complaint_at_visit, soap_subjective, soap_objective, soap_assessment, soap_plan )",
          )
          .eq("visit_id", visitId)
          .eq("clinic_patient_id", patientId)
          .maybeSingle()
      : appointmentId
        ? supabase
            .from("visit")
            .select(
              "visit_id, status, created_at, clinical_record ( chief_complaint_at_visit, soap_subjective, soap_objective, soap_assessment, soap_plan )",
            )
            .eq("appointment_id", appointmentId)
            .order("created_at", { ascending: false })
            .limit(1)
            .maybeSingle()
        : Promise.resolve({ data: null }),
    // Lịch sử khám các đợt TRƯỚC của BN (feedback C5#4) — đọc qua RLS, read-only.
    supabase
      .from("visit")
      .select(
        "visit_id, status, created_at, appointment_id, service:service_type!service_type_id ( name ), doctor:staff!attending_doctor_id ( full_name ), clinical_record ( chief_complaint_at_visit, soap_assessment )",
      )
      .eq("clinic_patient_id", patientId)
      .order("created_at", { ascending: false })
      .limit(8),
  ]);

  // Bỏ chính lượt khám đang mở; gói gọn để hiển thị.
  const history = ((historyRes.data as HistoryVisitRow[] | null) ?? [])
    .filter((v) => v.appointment_id !== appointmentId)
    .map((v) => {
      const cr = one(v.clinical_record);
      return {
        visit_id: v.visit_id,
        created_at: v.created_at,
        status: v.status,
        service: one(v.service)?.name ?? null,
        doctor: one(v.doctor)?.full_name ?? null,
        chief_complaint: cr?.chief_complaint_at_visit ?? "",
        assessment: cr ? flatten(cr.soap_assessment) : "",
      };
    });

  const visit = (visitRes.data as VisitRow | null) ?? null;
  const cr = visit
    ? Array.isArray(visit.clinical_record)
      ? visit.clinical_record[0]
      : visit.clinical_record
    : null;

  // Đơn thuốc đã kê cho lượt khám này (để prefill form kê thuốc của bác sĩ).
  let prescriptions: {
    drug_name_raw: string | null;
    quantity: string | null;
    dosage_instructions: string | null;
    caution: string | null;
  }[] = [];
  if (visit?.visit_id) {
    const { data: rx } = await supabase
      .from("prescription")
      .select("drug_name_raw, quantity, dosage_instructions, caution")
      .eq("visit_id", visit.visit_id)
      .order("created_at", { ascending: true });
    prescriptions = rx ?? [];
  }

  return NextResponse.json({
    profile: profileRes.data ?? null,
    pregnancy: pregRes.data ?? null,
    labs: labRes.data ?? [],
    history,
    prescriptions,
    visit: visit ? { visit_id: visit.visit_id, status: visit.status, created_at: visit.created_at ?? null } : null,
    draft: {
      chief_complaint: cr?.chief_complaint_at_visit ?? "",
      subjective: cr?.soap_subjective ?? null,
      objective: cr?.soap_objective ?? null,
      assessment: cr?.soap_assessment ?? null,
      plan: cr?.soap_plan ?? null,
    },
  });
}

interface PostBody {
  appointmentId?: string;
  clinicPatientId?: string;
  chief_complaint?: string;
  subjective?: unknown;
  objective?: unknown;
  assessment?: unknown;
  plan?: unknown;
  // Tiền sử (mục III/IV) — patient-level, bác sĩ xác nhận/cập nhật.
  profile?: {
    allergies?: string[];
    blood_type?: string | null;
    chronic_diseases?: string[];
    surgical_history?: string[];
    current_medications?: string[];
    family_history?: unknown;
    notes?: string | null;
  };
  // Đơn thuốc bác sĩ kê (free-text) — thay TOÀN BỘ đơn của lượt khám này.
  prescriptions?: Array<{
    drug_name?: string;
    quantity?: string;
    dosage?: string;
    caution?: string;
  }>;
  // Điều dưỡng: chỉ ghi Sinh hiệu (objective.vitals), KHÔNG đụng mục khác.
  vitalsOnly?: boolean;
}

/** Lọc bỏ key rỗng (null / chuỗi trắng) — để merge chỉ ghi đè bằng giá trị thật. */
export async function POST(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  let body: PostBody;
  try {
    body = (await request.json()) as PostBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const vitalsOnly = body.vitalsOnly === true;

  const role = await getClinicRole();
  // GHI LÂM SÀNG = Bác sĩ + Thư ký Y khoa (nhập hộ) ghi FULL hồ sơ; ĐIỀU DƯỠNG
  // (vitalsOnly) chỉ ghi Sinh hiệu + lý do khám. Lễ tân/Quản lý KHÔNG ghi lâm sàng
  // (check-in/hành chính tách riêng ở /api/appointments — vẫn canCheckin).
  // TKYK + Điều dưỡng được NHẬP hồ sơ như bác sĩ (mở quyền 29/6); finalize vẫn gate riêng.
  // RECEPTION chỉ được ghi sinh hiệu (vitalsOnly) lúc check-in.
  const allowed =
    isDoctorRole(role) ||
    isThuKyRole(role) ||
    isNurseRole(role) ||
    (vitalsOnly && role === "RECEPTION");
  if (!allowed) {
    return NextResponse.json(
      {
        error: vitalsOnly
          ? "Chỉ bác sĩ / điều dưỡng / lễ tân mới ghi sinh hiệu + lý do khám."
          : "Chỉ bác sĩ mới ghi hồ sơ khám.",
      },
      { status: 403 },
    );
  }

  const appointmentId = (body.appointmentId ?? "").trim();
  const clinicPatientId = (body.clinicPatientId ?? "").trim();
  if (!appointmentId || !clinicPatientId) {
    return NextResponse.json(
      { error: "Thiếu lịch hẹn hoặc bệnh nhân." },
      { status: 400 },
    );
  }

  // Every gate — arrival, ownership, the 48h lock, the writable-status
  // whitelist, the objective merge that protects the nurse's vitals — lives in
  // FastAPI, and the whole write is one transaction instead of five statements.
  return proxyJsonToBackend("POST", "/api/v1/clinical-records", {
    appointment_id: appointmentId,
    clinic_patient_id: clinicPatientId,
    vitals_only: vitalsOnly,
    chief_complaint: body.chief_complaint ?? null,
    subjective: body.subjective ?? null,
    ...(body.objective !== undefined ? { objective: body.objective } : {}),
    assessment: body.assessment ?? null,
    plan: body.plan ?? null,
    profile: body.profile ?? null,
    prescriptions: body.prescriptions ?? null,
  });
}
