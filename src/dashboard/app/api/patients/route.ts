// CSKH / Lễ tân patient intake. RLS on `patient` only has a SELECT policy, so
// authenticated INSERTs are denied — we write with the service-role client.
// Access control = shared session + an intake role cookie (CSKH/RECEPTION/MGMT).
//
//   POST { full_name, date_of_birth?, phone_primary?, phone_secondary?,
//          national_id_number?, location_id, force? }
//     → { duplicate: true, matches: [...] }   when phone already exists & !force
//     → { ok: true, patient: {...} }          on insert

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getSupabaseService } from "../../../lib/supabase-service";
import {
  patientEditViaBackend,
  proxyJsonToBackend,
} from "../../../lib/backend-proxy";
import { getClinicRole, getClinicStaffId } from "../../../lib/clinic-session";
import { canWriteIntake, canEditPatient } from "../../../lib/roles";
import { PHONE_RE, CCCD_RE } from "../../../lib/validation";
import { logEvent } from "../../../lib/event-log";

interface Body {
  full_name?: string;
  date_of_birth?: string;
  // Năm sinh khi BN chỉ nhớ năm (feedback B5#4). Cần migration 040; nếu chưa
  // apply, insert dưới bắt lỗi cột thiếu → bỏ birth_year, giữ date_of_birth.
  birth_year?: number | string;
  phone_primary?: string;
  phone_secondary?: string;
  national_id_number?: string;
  location_id?: string;
  // Hành chính (mục I form khám) — đồng bộ sang hồ sơ lâm sàng.
  gender?: string;
  ethnicity?: string;
  nationality?: string;
  occupation?: string;
  patient_objection?: string;
  address?: string;
  // Địa chỉ có cấu trúc sau sáp nhập (tỉnh → phường, bỏ huyện).
  province_code?: string;
  province_name?: string;
  ward_code?: string;
  ward_name?: string;
  address_detail?: string;
  // CSKH khai thác lúc đặt lịch: "Vấn đề khiến BN đi khám" (KHÁC chief_complaint
  // của BS) + "Lĩnh vực" (mã chuyên khoa PK/SK/NT/HMVS/NK).
  van_de_di_kham?: string;
  linh_vuc?: string;
  guardian_name?: string;
  force?: boolean;
}

/** Trim → null nếu rỗng. */
function nn(v: string | undefined): string | null {
  const t = (v ?? "").trim();
  return t || null;
}

// Patient creation has exactly one business-logic owner: FastAPI. A backend
// outage must fail closed so MPI/dedup and schema validation are never bypassed.
const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

export async function POST(request: Request) {
  // Must hold the shared session AND an intake role.
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

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  // Validate-FORMAT thân thiện Ở ĐÂY (fail nhanh, tiếng Việt) TRƯỚC khi proxy.
  // LUẬT NGHIỆP VỤ (chống trùng SĐT/CCCD, sinh mã BN, MPI, ghi DB) do FastAPI lo
  // — nguồn-sự-thật duy nhất cho việc tạo BN, app khác (mobile…) dùng chung.
  const full_name = (body.full_name ?? "").trim();
  const location_id = (body.location_id ?? "").trim();
  const phone_primary = (body.phone_primary ?? "").trim() || null;
  const phone_secondary = (body.phone_secondary ?? "").trim() || null;
  const national = (body.national_id_number ?? "").trim() || null;
  if (!full_name) {
    return NextResponse.json({ error: "Phải nhập họ tên." }, { status: 400 });
  }
  if (!location_id) {
    return NextResponse.json({ error: "Phải chọn cơ sở." }, { status: 400 });
  }
  if (phone_primary && !PHONE_RE.test(phone_primary)) {
    return NextResponse.json(
      { error: "SĐT chính không hợp lệ (10 số, bắt đầu bằng 0; đầu số 02/03/05/07/08/09)." },
      { status: 400 },
    );
  }
  if (phone_secondary && !PHONE_RE.test(phone_secondary)) {
    return NextResponse.json(
      { error: "SĐT người nhà không hợp lệ (10 số, bắt đầu bằng 0; đầu số 02/03/05/07/08/09)." },
      { status: 400 },
    );
  }
  if (national && !CCCD_RE.test(national)) {
    return NextResponse.json(
      { error: "CCCD phải gồm đúng 12 chữ số (3 số đầu là mã tỉnh 001–096)." },
      { status: 400 },
    );
  }

  if (!API_BASE) {
    return NextResponse.json(
      { error: "CLINIC_API_URL chưa được cấu hình; không thể tạo bệnh nhân an toàn." },
      { status: 503 },
    );
  }

  const {
    data: { session },
  } = await caller.auth.getSession();
  const token = session?.access_token;
  if (!token) {
    return NextResponse.json({ error: "Phiên đăng nhập đã hết hạn." }, { status: 401 });
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15_000);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1/patients`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: controller.signal,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      {
        error:
          "Không kết nối được máy chủ xử lý. Hồ sơ chưa được tạo; vui lòng thử lại.",
      },
      { status: 502 },
    );
  } finally {
    clearTimeout(timeout);
  }

  let json: {
    duplicate?: boolean;
    matches?: unknown;
    clinic_patient_id?: string;
    patient_code?: string;
    full_name?: string;
    detail?: string;
    error?: string;
    message?: string;
  };
  try {
    json = await res.json();
  } catch {
    return NextResponse.json(
      { error: "Máy chủ trả dữ liệu không đọc được. Hồ sơ chưa được tạo." },
      { status: 502 },
    );
  }

  if (res.status === 200 && json.duplicate) {
    return NextResponse.json({ duplicate: true, matches: json.matches ?? [] });
  }
  if (!res.ok) {
    const msg =
      json.message || json.detail || json.error || "Không tạo được bệnh nhân.";
    return NextResponse.json({ error: msg }, { status: res.status });
  }

  const auditDb = getSupabaseService();
  if (auditDb && json.clinic_patient_id) {
    await logEvent(auditDb, {
      event_type: "patient.created",
      aggregate_type: "patient",
      aggregate_id: json.clinic_patient_id,
      payload: {
        clinic_patient_id: json.clinic_patient_id,
        patient_code: json.patient_code,
        full_name,
        date_of_birth: (body.date_of_birth ?? "").trim() || null,
        phone_primary,
        phone_secondary,
        national_id_number: national,
        location_id,
      },
      metadata: {
        clinic_role: role,
        clinic_staff_id: staffId,
        actor_auth_user_id: user.id,
        origin: "dashboard:patient-intake",
      },
    });
  }

  return NextResponse.json({
    ok: true,
    patient: {
      clinic_patient_id: json.clinic_patient_id,
      patient_code: json.patient_code,
      full_name: json.full_name,
    },
  });
}

// PATCH { clinic_patient_id, full_name?, date_of_birth?, phone_primary?,
//         phone_secondary?, location_id? } → cập nhật thông tin BN (CSKH/Lễ tân/QL).
// Không đụng national_id_number (D-identity). Ghi qua service-role.
interface PatchBody {
  clinic_patient_id?: string;
  full_name?: string;
  date_of_birth?: string;
  phone_primary?: string;
  phone_secondary?: string;
  location_id?: string;
  gender?: string;
  ethnicity?: string;
  nationality?: string;
  occupation?: string;
  patient_objection?: string;
  address?: string;
  guardian_name?: string;
}

export async function PATCH(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const role = await getClinicRole();
  // SỬA hồ sơ hành chính: intake (CSKH/Lễ tân/QL/ĐD) + BÁC SĨ. (Tạo mới = POST
  // vẫn chỉ canWriteIntake — bác sĩ không tạo BN, chỉ sửa.)
  if (!canEditPatient(role)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  let body: PatchBody;
  try {
    body = (await request.json()) as PatchBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.clinic_patient_id ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id bệnh nhân." }, { status: 400 });

  const full_name = (body.full_name ?? "").trim();
  if (!full_name) {
    return NextResponse.json({ error: "Phải nhập họ tên." }, { status: 400 });
  }
  // Quy tắc nhập liệu CỨNG (server-side): SĐT 10 số.
  const editPhone = (body.phone_primary ?? "").trim();
  const editPhone2 = (body.phone_secondary ?? "").trim();
  if (editPhone && !PHONE_RE.test(editPhone)) {
    return NextResponse.json(
      { error: "SĐT chính không hợp lệ (10 số, bắt đầu bằng 0; đầu số 02/03/05/07/08/09)." },
      { status: 400 },
    );
  }
  if (editPhone2 && !PHONE_RE.test(editPhone2)) {
    return NextResponse.json(
      { error: "SĐT người nhà không hợp lệ (10 số, bắt đầu bằng 0; đầu số 02/03/05/07/08/09)." },
      { status: 400 },
    );
  }

  // W5 (ADR-0012): PATCH /api/v1/patients/{id} owns this now. It is scoped to
  // the caller's clinic — this path updated by clinic_patient_id alone, which
  // reaches every clinic once there is more than one. Off until
  // PATIENT_EDIT_VIA_BACKEND=1.
  if (patientEditViaBackend()) {
    return proxyJsonToBackend("PATCH", `/api/v1/patients/${id}`, {
      full_name,
      date_of_birth: (body.date_of_birth ?? "").trim() || null,
      phone_primary: (body.phone_primary ?? "").trim() || null,
      phone_secondary: (body.phone_secondary ?? "").trim() || null,
      gender: nn(body.gender),
      ethnicity: nn(body.ethnicity),
      nationality: nn(body.nationality),
      occupation: nn(body.occupation),
      patient_objection: nn(body.patient_objection),
      address: nn(body.address),
      guardian_name: nn(body.guardian_name),
      ...((body.location_id ?? "").trim()
        ? { location_id: (body.location_id ?? "").trim() }
        : {}),
    });
  }

  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }

  const patch: Record<string, string | null> = {
    full_name,
    date_of_birth: (body.date_of_birth ?? "").trim() || null,
    phone_primary: (body.phone_primary ?? "").trim() || null,
    phone_secondary: (body.phone_secondary ?? "").trim() || null,
    gender: nn(body.gender),
    ethnicity: nn(body.ethnicity),
    nationality: nn(body.nationality),
    occupation: nn(body.occupation),
    patient_objection: nn(body.patient_objection),
    address: nn(body.address),
    guardian_name: nn(body.guardian_name),
  };
  const loc = (body.location_id ?? "").trim();
  if (loc) patch.location_id = loc;

  const SEL =
    "clinic_patient_id, full_name, date_of_birth, phone_primary, phone_secondary, location_id, gender, ethnicity, nationality, occupation, patient_objection, address, guardian_name";

  // Đọc bản TRƯỚC để ghi vết before/after vào event_log (lưu mọi lần sửa hành chính —
  // yêu cầu Quang 29/6: sửa khi gõ sai nhưng log giữ tất cả). Best-effort.
  const { data: before } = await db
    .from("patient")
    .select(SEL)
    .eq("clinic_patient_id", id)
    .maybeSingle();

  const { data, error } = await db
    .from("patient")
    .update(patch)
    .eq("clinic_patient_id", id)
    .select(SEL)
    .maybeSingle();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!data) {
    return NextResponse.json({ error: "Không tìm thấy bệnh nhân." }, { status: 404 });
  }

  // Chỉ ghi các TRƯỜNG thực sự đổi (from → to) cho gọn + dễ truy vết.
  const beforeRec = (before ?? {}) as Record<string, unknown>;
  const afterRec = data as Record<string, unknown>;
  const changes: Record<string, { from: unknown; to: unknown }> = {};
  for (const k of Object.keys(patch)) {
    if (beforeRec[k] !== afterRec[k]) {
      changes[k] = { from: beforeRec[k] ?? null, to: afterRec[k] ?? null };
    }
  }

  await logEvent(db, {
    event_type: "patient.updated",
    aggregate_type: "patient",
    aggregate_id: id,
    payload: { clinic_patient_id: id, changes },
    metadata: {
      clinic_role: role,
      actor_auth_user_id: user.id,
      origin: "dashboard:patient-edit",
    },
  });

  return NextResponse.json({ ok: true, patient: data });
}
