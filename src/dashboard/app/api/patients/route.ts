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

// FastAPI base URL. Server-only (lời gọi đi TỪ server, không phải trình duyệt) →
// không CORS, giữ BACKEND_API_KEY ở server. Khớp cách /api/brief gọi backend.
//
// KHÁC /api/brief: ở production (Vercel) CHƯA deploy FastAPI → CLINIC_API_URL
// rỗng. Khi đó BỎ QUA proxy và tạo BN TRỰC TIẾP qua Supabase service-role
// (fallback bên dưới), thay vì cứng nhắc gọi localhost:8000 rồi 502. Khi FastAPI
// đã deploy, set CLINIC_API_URL → tự quay lại đường proxy (MPI/dedup ở backend).
const API_BASE = (process.env.CLINIC_API_URL ?? "").trim();

/** Sinh mã BN dạng BN-YYYY-XXXXXX (mirror _generate_patient_code của FastAPI). */
function generatePatientCode(attempt = 0): string {
  const now = new Date();
  // JS không có micro-giây như Python; dùng ms trong ngày + jitter theo attempt.
  const ms = now.getHours() * 3600000 + now.getMinutes() * 60000 +
    now.getSeconds() * 1000 + now.getMilliseconds();
  const seq = (ms * 7 + attempt * 7919) % 1_000_000;
  return `BN-${now.getFullYear()}-${String(seq).padStart(6, "0")}`;
}

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

  // ĐƯỜNG 1 — Proxy sang FastAPI (nếu CLINIC_API_URL đã set). server→server:
  // không CORS, giữ key ở server. Forward toàn bộ body — DTO backend tự chuẩn
  // hoá (birth_year→dob, whitelist…). Nếu BACKEND không kết nối được → KHÔNG
  // 502, mà rơi xuống ĐƯỜNG 2 (tạo trực tiếp qua Supabase) để PK vẫn dùng được.
  if (API_BASE) {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    const apiKey = process.env.BACKEND_API_KEY;
    if (apiKey) headers["X-API-Key"] = apiKey;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15_000);
    let res: Response | null = null;
    try {
      res = await fetch(`${API_BASE}/api/v1/patients`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal: controller.signal,
        cache: "no-store",
      });
    } catch {
      res = null; // backend không kết nối được → fallback bên dưới.
    } finally {
      clearTimeout(timeout);
    }

    if (res) {
      let json: {
        duplicate?: boolean;
        matches?: unknown;
        clinic_patient_id?: string;
        patient_code?: string;
        full_name?: string;
        error?: string;
        message?: string;
      };
      try {
        json = await res.json();
      } catch {
        return NextResponse.json(
          { error: "Máy chủ trả dữ liệu không đọc được." },
          { status: 502 },
        );
      }

      // Trùng SĐT (chưa force): FastAPI trả 200 {duplicate, matches} — KHÔNG tạo.
      if (res.status === 200 && json.duplicate) {
        return NextResponse.json({ duplicate: true, matches: json.matches ?? [] });
      }
      if (!res.ok) {
        const msg = json.message || json.error || "Không tạo được bệnh nhân.";
        return NextResponse.json({ error: msg }, { status: res.status });
      }

      // Tạo thành công (201). Ghi AUDIT Ở NEXT (chỉ Next có actor-context).
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
  }

  // ĐƯỜNG 2 — Tạo BN TRỰC TIẾP qua Supabase service-role (FastAPI chưa deploy
  // hoặc không kết nối được). Mirror logic FastAPI: 1) CCCD hard-conflict 409,
  // 2) SĐT soft-block (duplicate) khi !force, 3) insert + sinh patient_code.
  // MPI dedup (best-effort ở backend) BỎ trong đường này — khi có FastAPI sẽ
  // tự chạy lại qua ĐƯỜNG 1.
  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }

  // 1) CCCD đã tồn tại → 409 (force KHÔNG override, cột UNIQUE).
  if (national) {
    const { data: cccdRow } = await db
      .from("patient")
      .select("patient_code, full_name")
      .eq("national_id_number", national)
      .limit(1)
      .maybeSingle();
    if (cccdRow) {
      return NextResponse.json(
        {
          error: `CCCD này đã có hồ sơ (${cccdRow.patient_code} · ${cccdRow.full_name}).`,
        },
        { status: 409 },
      );
    }
  }

  // 2) SĐT chính trùng & chưa force → cảnh báo, KHÔNG tạo (operator quyết định).
  if (phone_primary && !body.force) {
    const { data: dupes } = await db
      .from("patient")
      .select("clinic_patient_id, patient_code, full_name, date_of_birth")
      .eq("phone_primary", phone_primary)
      .limit(5);
    if (dupes && dupes.length > 0) {
      return NextResponse.json({ duplicate: true, matches: dupes });
    }
  }

  // 3) Insert. Dựng record đầy đủ; cột nào chưa migrate (birth_year, province…)
  // sẽ bị PostgREST báo thiếu → tự loại cột đó rồi thử lại (resilient).
  const birthYear =
    body.birth_year != null && `${body.birth_year}`.trim() !== ""
      ? Number.parseInt(`${body.birth_year}`, 10)
      : null;
  const record: Record<string, unknown> = {
    full_name,
    date_of_birth: (body.date_of_birth ?? "").trim() || null,
    phone_primary,
    phone_secondary,
    national_id_number: national,
    location_id,
    is_active: true,
    gender: nn(body.gender),
    ethnicity: nn(body.ethnicity),
    nationality: nn(body.nationality),
    occupation: nn(body.occupation),
    patient_objection: nn(body.patient_objection),
    address: nn(body.address),
    guardian_name: nn(body.guardian_name),
    birth_year: Number.isNaN(birthYear) ? null : birthYear,
    province_code: nn(body.province_code),
    province_name: nn(body.province_name),
    ward_code: nn(body.ward_code),
    ward_name: nn(body.ward_name),
    address_detail: nn(body.address_detail),
    van_de_di_kham: nn(body.van_de_di_kham),
    linh_vuc: nn(body.linh_vuc),
  };

  let created: {
    clinic_patient_id?: string;
    patient_code?: string;
    full_name?: string;
  } | null = null;
  for (let attempt = 0; attempt < 12; attempt++) {
    const insert = { ...record, patient_code: generatePatientCode(attempt) };
    const { data, error } = await db
      .from("patient")
      .insert(insert)
      .select("clinic_patient_id, patient_code, full_name")
      .single();
    if (!error) {
      created = data;
      break;
    }
    // patient_code (hoặc CCCD) trùng → 23505.
    if (error.code === "23505") {
      if (/national_id/i.test(error.message)) {
        return NextResponse.json(
          { error: "CCCD này vừa được tạo cho hồ sơ khác." },
          { status: 409 },
        );
      }
      continue; // patient_code clash → sinh mã khác, thử lại.
    }
    // Cột chưa tồn tại trong schema cache (chưa migrate) → loại cột rồi thử lại.
    const missing = error.message.match(/'(\w+)' column/);
    if (missing && missing[1] in record) {
      delete record[missing[1]];
      attempt--; // không tính lần này vào quota retry mã.
      continue;
    }
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  if (!created) {
    return NextResponse.json(
      { error: "Không tạo được mã BN, thử lại." },
      { status: 500 },
    );
  }

  // AUDIT (best-effort) — cùng service-role client.
  await logEvent(db, {
    event_type: "patient.created",
    aggregate_type: "patient",
    aggregate_id: created.clinic_patient_id ?? "",
    payload: {
      clinic_patient_id: created.clinic_patient_id,
      patient_code: created.patient_code,
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
      origin: "dashboard:patient-intake:direct",
    },
  });

  return NextResponse.json({
    ok: true,
    patient: {
      clinic_patient_id: created.clinic_patient_id,
      patient_code: created.patient_code,
      full_name: created.full_name,
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
