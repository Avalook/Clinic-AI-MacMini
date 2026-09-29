// /api/clinical-record
//   GET  ?patientId=&appointmentId=  → data đồng bộ (tiền sử/thai/XN) + bản NHÁP
//        hồ sơ khám của lịch này (để prefill phần bác sĩ điền).
//   POST { appointmentId, clinicPatientId, draft } → LƯU NHÁP hồ sơ khám.
//
// AN TOÀN (TT13/2011/TT-BYT): chỉ ghi vào visit OPEN/IN_PROGRESS; nếu visit đã
// FINALIZED → 409 (luật cấm sửa, phải đính chính). KHÔNG bao giờ tự set FINALIZED.

import { NextResponse } from "next/server";
import {
  sinhHieuTheoKhoaPhieu,
  type DongSinhHieu,
} from "@/lib/sinh-hieu-dong-bo";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { docTuBackend, proxyJsonToBackend } from "../../../lib/backend-proxy";

/** Dữ liệu thô backend trả (`GET /api/v1/clinical-records/doc`, 24/09/2026). */
interface HoSoTho {
  revision: number;
  prescription_draft: unknown;
  profile: unknown;
  pregnancy: unknown;
  labs: unknown[];
  history_raw: {
    visit_id: string;
    status: string;
    created_at: string;
    service: string | null;
    doctor: string | null;
    chief_complaint_at_visit: string | null;
    soap_assessment: unknown;
  }[];
  prescriptions: unknown[];
  vital_latest: DongSinhHieu | null;
  // `phieu_v5`: lượt ghi phiếu khám v5 (29/09/2026) — màn bệnh án mở phiếu v5 chỉ-xem.
  visit: { visit_id: string; status: string; created_at: string | null; phieu_v5?: boolean } | null;
  draft: {
    chief_complaint: string;
    subjective: unknown;
    objective: unknown;
    assessment: unknown;
    plan: unknown;
  };
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


export async function GET(request: Request) {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const url = new URL(request.url);
  const patientId = url.searchParams.get("patientId");
  const appointmentId = url.searchParams.get("appointmentId");
  const visitId = url.searchParams.get("visitId");
  if (!patientId) {
    return NextResponse.json({ error: "Thiếu patientId." }, { status: 400 });
  }

  // 24/09/2026: ĐỌC + ai được xem (quyền đọc hồ sơ, thư ký chỉ khách của bác sĩ
  // mình) ở backend (`services/ho_so_lam_sang_doc.py`). Trang này từng tự đọc
  // bảy bảng bằng Supabase. Ở đây chỉ còn GHÉP Ô HIỂN THỊ.
  const q = new URLSearchParams({ patient_id: patientId });
  if (appointmentId) q.set("appointment_id", appointmentId);
  if (visitId) q.set("visit_id", visitId);
  const doc = await docTuBackend<HoSoTho>(`/api/v1/clinical-records/doc?${q.toString()}`);
  if (!doc.ok) return doc.res;
  const d = doc.data;

  const history = d.history_raw.map((v) => ({
    visit_id: v.visit_id,
    created_at: v.created_at,
    status: v.status,
    service: v.service,
    doctor: v.doctor,
    chief_complaint: v.chief_complaint_at_visit ?? "",
    assessment: flatten(v.soap_assessment),
  }));

  // Số đo mới nhất ghép vào ô sinh hiệu của phiếu (trình bày).
  let objective = (d.draft.objective ?? null) as Record<string, unknown> | null;
  const tuDo = sinhHieuTheoKhoaPhieu(d.vital_latest);
  if (Object.keys(tuDo).length > 0) {
    const cu = (objective ?? {}) as Record<string, unknown>;
    const vitalsCu =
      cu.vitals && typeof cu.vitals === "object" ? (cu.vitals as Record<string, unknown>) : {};
    objective = { ...cu, vitals: { ...vitalsCu, ...tuDo } };
  }

  return NextResponse.json({
    revision: d.revision ?? 0,
    prescription_draft: d.prescription_draft ?? null,
    profile: d.profile ?? null,
    pregnancy: d.pregnancy ?? null,
    labs: d.labs ?? [],
    history,
    prescriptions: d.prescriptions ?? [],
    visit: d.visit,
    draft: { ...d.draft, objective },
  });
}

interface PostBody {
  expectedRevision?: number;
  approvePrescriptionDraft?: boolean;
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
    id?: string;
    drug_catalog_id?: string | null;
    drug_name?: string;
    quantity?: string;
    dosage?: string;
    caution?: string;
  }>;
  // CP6: lý do đính chính khi sửa / bỏ dòng đơn nhà thuốc / thu ngân đã đụng tới.
  prescriptionCorrectionReason?: string;
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

  // Ai ghi được bệnh án là QUYỀN `clinical.record.write`, backend hỏi trong
  // chính giao dịch ghi (CORE-B3, 23/09/2026). Proxy không gác vai nữa — gác ở
  // đây là hệ quyền thứ hai, và là luật nghiệp vụ trong TSX.

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
    expected_revision: body.expectedRevision,
    approve_prescription_draft: body.approvePrescriptionDraft === true,
    chief_complaint: body.chief_complaint ?? null,
    subjective: body.subjective ?? null,
    ...(body.objective !== undefined ? { objective: body.objective } : {}),
    assessment: body.assessment ?? null,
    plan: body.plan ?? null,
    profile: body.profile ?? null,
    prescriptions: body.prescriptions ?? null,
    prescription_correction_reason: body.prescriptionCorrectionReason ?? null,
  });
}
