// /api/clinical-record
//   GET  ?patientId=&appointmentId=  → data đồng bộ (tiền sử/thai/XN) + bản NHÁP
//        hồ sơ khám của lịch này (để prefill phần bác sĩ điền).
//   POST { appointmentId, clinicPatientId, draft } → LƯU NHÁP hồ sơ khám.
//
// AN TOÀN (TT13/2011/TT-BYT): chỉ ghi vào visit OPEN/IN_PROGRESS; nếu visit đã
// FINALIZED → 409 (luật cấm sửa, phải đính chính). KHÔNG bao giờ tự set FINALIZED.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getSupabaseService } from "../../../lib/supabase-service";
import {
  clinicalRecordViaBackend,
  proxyJsonToBackend,
} from "../../../lib/backend-proxy";
import { getClinicRole, getClinicStaffId } from "../../../lib/clinic-session";
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

function asObj(x: unknown): Record<string, unknown> {
  return x && typeof x === "object" && !Array.isArray(x)
    ? (x as Record<string, unknown>)
    : {};
}

/** Lọc bỏ key rỗng (null / chuỗi trắng) — để merge chỉ ghi đè bằng giá trị thật. */
function nonEmpty(o: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(o)) {
    if (v == null) continue;
    if (typeof v === "string" && v.trim() === "") continue;
    out[k] = v;
  }
  return out;
}

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
  const staffId = await getClinicStaffId();

  const appointmentId = (body.appointmentId ?? "").trim();
  const clinicPatientId = (body.clinicPatientId ?? "").trim();
  if (!appointmentId || !clinicPatientId) {
    return NextResponse.json(
      { error: "Thiếu lịch hẹn hoặc bệnh nhân." },
      { status: 400 },
    );
  }

  // W5 (ADR-0012): every gate below — arrival, ownership, the 48h lock, the
  // writable-status whitelist, the objective merge that protects the nurse's
  // vitals — now lives in FastAPI, and the whole write is one transaction
  // instead of five statements. Off until CLINICAL_RECORD_VIA_BACKEND=1.
  if (clinicalRecordViaBackend()) {
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

  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }

  // GATE lễ tân check-in TRƯỚC khi điền sinh hiệu (vitalsOnly): điều dưỡng/lễ tân
  // chỉ ghi sinh hiệu SAU khi lễ tân đã check-in (BN đã đến). CHECKED_IN = đang
  // khám; COMPLETED = cho sửa lại khi visit chưa FINALIZED. Trước đó (SCHEDULED/
  // CSKH_CONFIRMED/CONFIRMED) → chặn tại server (khớp arrivalPending ở form).
  if (vitalsOnly) {
    const { data: ap } = await db
      .from("appointment")
      .select("status")
      .eq("id", appointmentId)
      .maybeSingle();
    const st = (ap as { status: string | null } | null)?.status ?? null;
    if (st !== "CHECKED_IN" && st !== "COMPLETED") {
      return NextResponse.json(
        { error: "Chờ lễ tân check-in bệnh nhân (đã đến) trước khi điền sinh hiệu." },
        { status: 409 },
      );
    }
  }

  // OWNERSHIP hồ sơ ĐẦY ĐỦ: bác sĩ (DOCTOR/ULTRASOUND_DOCTOR) chỉ ghi hồ sơ khám
  // cho lịch của CHÍNH MÌNH hoặc lịch CHƯA PHÂN bác sĩ (walk-in). CHẶN khi lịch đã
  // gán cho BÁC SĨ KHÁC (tránh ghi nhầm/đè hồ sơ BN của người khác). Miễn trừ:
  // TKYK (nhập hộ mọi BS — rủi ro đã chấp nhận), điều dưỡng (float, ghi hộ),
  // vitalsOnly (đón khám, ai cũng ghi sinh hiệu được). Khớp guard appointments PATCH.
  if (!vitalsOnly && isDoctorRole(role) && role !== "TKYK") {
    const { data: apOwn } = await db
      .from("appointment")
      .select("doctor_id")
      .eq("id", appointmentId)
      .maybeSingle();
    const ownerId = (apOwn as { doctor_id: string | null } | null)?.doctor_id ?? null;
    if (ownerId && ownerId !== staffId) {
      return NextResponse.json(
        { error: "Lịch hẹn này thuộc bác sĩ khác — không thể ghi hồ sơ khám." },
        { status: 403 },
      );
    }
  }

  // Tìm lượt khám gắn với lịch hẹn này.
  const { data: existing, error: findErr } = await db
    .from("visit")
    .select("visit_id, status, created_at")
    .eq("appointment_id", appointmentId)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (findErr) {
    return NextResponse.json({ error: findErr.message }, { status: 500 });
  }

  // 48h lock: không cho sửa hồ sơ đã tạo quá 48 tiếng (≈ 2 ca trực). Truyến
  // ca/đính chính phải qua Trưởng ca — ché độ đầu đảm bảo touàn vẹn hồ sơ.
  if (existing) {
    const visitCreatedAt = (existing as Record<string, unknown>).created_at as string | null;
    if (visitCreatedAt) {
      const ageMs = Date.now() - new Date(visitCreatedAt).getTime();
      if (ageMs > 48 * 3_600_000) {
        return NextResponse.json(
          { error: "Hồ sơ đã khóa sau 48h — không thể chỉnh sửa. Liên hệ Trưởng ca nếu cần đính chính." },
          { status: 403 },
        );
      }
    }
  }

  let visitId = existing?.visit_id ?? null;
  // Chỉ cho ghi vào lượt khám ĐANG MỞ. FINALIZED *và* AMENDED đều bất biến theo
  // TT13 — sửa phải qua visit_amendment, KHÔNG ghi đè trực tiếp (whitelist thay vì
  // chỉ chặn FINALIZED, tránh lọt AMENDED).
  const WRITABLE_VISIT_STATUSES = ["OPEN", "IN_PROGRESS"];
  if (existing && !WRITABLE_VISIT_STATUSES.includes(existing.status)) {
    return NextResponse.json(
      {
        error: `Hồ sơ đã chốt (${existing.status}) — luật cấm sửa, phải đính chính.`,
      },
      { status: 409 },
    );
  }

  // Chưa có lượt khám → tạo NHÁP (IN_PROGRESS), KHÔNG chốt.
  if (!visitId) {
    // Điều dưỡng / Thư ký Y khoa tạo nháp: bác sĩ phụ trách = bác sĩ của LỊCH HẸN
    // (KHÔNG phải người đang nhập). Chỉ BÁC SĨ tự ghi mới lấy staffId làm attending.
    let attendingId: string | null = staffId;
    if (vitalsOnly || isThuKyRole(role) || isNurseRole(role)) {
      const { data: ap } = await db
        .from("appointment")
        .select("doctor_id")
        .eq("id", appointmentId)
        .maybeSingle();
      attendingId = (ap?.doctor_id as string | null) ?? null;
    }
    const { data: created, error: vErr } = await db
      .from("visit")
      .insert({
        clinic_patient_id: clinicPatientId,
        appointment_id: appointmentId,
        attending_doctor_id: attendingId,
        status: "IN_PROGRESS",
        // Mốc BẮT ĐẦU lượt khám (đón khách/nhập sinh hiệu) — nuôi "đồng hồ chờ" ở
        // board Lễ tân (VisitStatusBoard/WaitClock). CHỈ set 1 lần lúc TẠO visit
        // (block này chỉ chạy khi chưa có visit) — lần lưu sau KHÔNG ghi đè.
        // Luồng import/FastAPI cũng set cột này; dashboard trước đây bỏ trống → đồng
        // hồ hiện "—". KHÔNG đụng visit.status/FINALIZED/043.
        checked_in_at: new Date().toISOString(),
      })
      .select("visit_id")
      .single();
    if (vErr) {
      // RACE: 2 request (ĐD lưu sinh hiệu + bác sĩ lưu hồ sơ) cùng thấy "chưa có
      // visit" → cùng INSERT. Khi có UNIQUE(appointment_id) (migration 039), cái
      // sau dính 23505 → tìm lại visit của request kia thay vì tạo trùng.
      if (vErr.code === "23505") {
        const { data: again } = await db
          .from("visit")
          .select("visit_id, status")
          .eq("appointment_id", appointmentId)
          .order("created_at", { ascending: false })
          .limit(1)
          .maybeSingle();
        if (!again) {
          return NextResponse.json({ error: vErr.message }, { status: 500 });
        }
        if (!WRITABLE_VISIT_STATUSES.includes(again.status)) {
          return NextResponse.json(
            { error: `Hồ sơ đã chốt (${again.status}) — luật cấm sửa.` },
            { status: 409 },
          );
        }
        visitId = again.visit_id;
      } else {
        return NextResponse.json({ error: vErr.message }, { status: 500 });
      }
    } else {
      visitId = created.visit_id;
    }
  }

  // Điều dưỡng: merge Sinh hiệu vào soap_objective + (D25) "Lý do khám bệnh"
  // (BS đưa ra, ĐD nhập hộ → chief_complaint_at_visit). KHÔNG đụng các mục khác
  // (chuẩn đoán/lời dặn/tiền sử của bác sĩ giữ nguyên). Lý do CHỈ ghi khi ĐD có
  // nhập (non-empty) → tránh save sinh hiệu rỗng xoá mất lý do bác sĩ đã ghi.
  if (vitalsOnly) {
    const { data: cr } = await db
      .from("clinical_record")
      .select("soap_objective")
      .eq("visit_id", visitId)
      .maybeSingle();
    const merged = {
      ...asObj(cr?.soap_objective),
      vitals: asObj(body.objective).vitals ?? {},
    };
    const cc = (body.chief_complaint ?? "").trim();
    const patch: Record<string, unknown> = { soap_objective: merged };
    if (cc) patch.chief_complaint_at_visit = cc;
    const { error } = cr
      ? await db
          .from("clinical_record")
          .update(patch)
          .eq("visit_id", visitId)
      : await db
          .from("clinical_record")
          .insert({ visit_id: visitId, ...patch });
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true, visit_id: visitId, vitalsOnly: true });
  }

  // Bác sĩ lưu: KHÔNG ghi đè trọn soap_objective. Đọc bản hiện có rồi MERGE để
  // GIỮ Sinh hiệu điều dưỡng vừa nhập — bác sĩ có thể đã mở form TRƯỚC khi ĐD nhập
  // sinh hiệu → prefill cũ rỗng, lưu blind sẽ xoá sạch (mất dữ liệu lâm sàng).
  // vitals: giữ giá trị DB, chỉ ghi đè bằng ô KHÔNG RỖNG của bác sĩ.
  const { data: crPrev } = await db
    .from("clinical_record")
    .select("soap_objective")
    .eq("visit_id", visitId)
    .maybeSingle();
  const prevObj = asObj(crPrev?.soap_objective);
  const inObj = asObj(body.objective);
  const mergedObjective =
    body.objective == null && Object.keys(prevObj).length === 0
      ? null
      : {
          ...prevObj,
          ...inObj,
          vitals: { ...asObj(prevObj.vitals), ...nonEmpty(asObj(inObj.vitals)) },
        };

  // Upsert nội dung khám (clinical_record.visit_id UNIQUE).
  const { error: crErr } = await db.from("clinical_record").upsert(
    {
      visit_id: visitId,
      chief_complaint_at_visit: (body.chief_complaint ?? "").trim() || null,
      soap_subjective: body.subjective ?? null,
      soap_objective: mergedObjective,
      soap_assessment: body.assessment ?? null,
      soap_plan: body.plan ?? null,
    },
    { onConflict: "visit_id" },
  );
  if (crErr) return NextResponse.json({ error: crErr.message }, { status: 500 });

  // Tiền sử (patient-level) — upsert theo clinic_patient_id (UNIQUE). Không gate.
  if (body.profile) {
    const { error: pErr } = await db.from("patient_medical_profile").upsert(
      { clinic_patient_id: clinicPatientId, ...body.profile },
      { onConflict: "clinic_patient_id" },
    );
    if (pErr) return NextResponse.json({ error: pErr.message }, { status: 500 });
  }

  // Đơn thuốc: THAY toàn bộ đơn của lượt khám (xoá cũ → ghi mới). prescription
  // không phải bảng append-only nên DELETE được; ghi qua service-role.
  if (Array.isArray(body.prescriptions)) {
    await db.from("prescription").delete().eq("visit_id", visitId);
    const items = body.prescriptions
      .filter((p) => (p.drug_name ?? "").trim() !== "")
      .map((p, i) => ({
        source_ref: `dash-rx-${visitId}-${i}`,
        clinic_patient_id: clinicPatientId,
        visit_id: visitId,
        drug_name_raw: (p.drug_name ?? "").trim(),
        quantity: (p.quantity ?? "").trim() || null,
        dosage_instructions: (p.dosage ?? "").trim() || null,
        caution: (p.caution ?? "").trim() || null,
      }));
    if (items.length) {
      const { error: rxErr } = await db.from("prescription").insert(items);
      if (rxErr) {
        return NextResponse.json({ error: rxErr.message }, { status: 500 });
      }
    }
  }

  return NextResponse.json({ ok: true, visit_id: visitId });
}
