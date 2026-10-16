// CSKH / Lễ tân patient intake. RLS on `patient` only has a SELECT policy, so
// authenticated INSERTs are denied — we write with the service-role client.
// Access control = phiên đăng nhập ở đây; quyền do FastAPI quyết (27/09/2026).
//
//   POST { full_name, date_of_birth?, phone_primary?, phone_secondary?,
//          national_id_number?, email?, location_id, force? }
//     → { duplicate: true, matches: [...] }   when phone already exists & !force
//     → { ok: true, patient: {...} }          on insert

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";
import {
  PHONE_RE,
  CCCD_RE,
  emailError,
  tenError,
  dobErrorIso,
  homNayVn,
} from "../../../lib/validation";
import { ganCoSo } from "../../../lib/co-so";

interface Body {
  full_name?: string;
  date_of_birth?: string;
  // Năm sinh khi BN chỉ nhớ năm (feedback B5#4). Cần migration 040; nếu chưa
  // apply, insert dưới bắt lỗi cột thiếu → bỏ birth_year, giữ date_of_birth.
  birth_year?: number | string;
  phone_primary?: string;
  phone_secondary?: string;
  national_id_number?: string;
  email?: string;
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
  ly_do_trung_cccd?: string;
}

/** Trim → null nếu rỗng. */
function nn(v: string | null | undefined): string | null {
  const t = (v ?? "").trim();
  return t || null;
}

// Patient creation has exactly one business-logic owner: FastAPI. A backend
// outage must fail closed so MPI/dedup and schema validation are never bypassed.
const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

export async function POST(request: Request) {
  // Phiên đăng nhập ở đây; QUYỀN tạo hồ sơ backend quyết (cua_quyen
  // patient.create / booking.create / crm.manage — lego 11). Cửa vai
  // canWriteIntake cũ chặn người đã được cấp lego (kiểm toán 27/09/2026).
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

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
  const loiTen = tenError(full_name);
  if (loiTen) {
    return NextResponse.json({ error: loiTen }, { status: 400 });
  }
  if (!location_id) {
    return NextResponse.json({ error: "Phải chọn cơ sở." }, { status: 400 });
  }
  // Ngày sinh: dùng CHUNG luật với form (dobError), không viết lại luật ở đây.
  const loiNgaySinh = dobErrorIso(body.date_of_birth, homNayVn());
  if (loiNgaySinh) {
    return NextResponse.json({ error: loiNgaySinh }, { status: 400 });
  }
  if (phone_primary && !PHONE_RE.test(phone_primary)) {
    return NextResponse.json(
      { error: "SĐT chính không hợp lệ (10 số, bắt đầu bằng 0; đầu số 03/05/07/08/09)." },
      { status: 400 },
    );
  }
  if (phone_secondary && !PHONE_RE.test(phone_secondary)) {
    return NextResponse.json(
      { error: "SĐT người nhà không hợp lệ (10 số, bắt đầu bằng 0; đầu số 03/05/07/08/09)." },
      { status: 400 },
    );
  }
  if (national && !CCCD_RE.test(national)) {
    return NextResponse.json(
      { error: "CCCD phải gồm đúng 12 chữ số (3 số đầu là mã tỉnh 001–096)." },
      { status: 400 },
    );
  }

  // Email không bắt buộc; điền thì đúng định dạng (cùng luật máy chủ). Chặn ở
  // đây để người dùng luôn nhận câu tiếng Việt, không phải mảng lỗi 422 thô.
  const loiEmail = emailError(String(body.email ?? ""));
  if (loiEmail) {
    return NextResponse.json({ error: loiEmail }, { status: 400 });
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
  await ganCoSo(headers); // cơ sở đang đứng — lib/co-so.ts

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
    cccd_trung?: boolean;
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
    return NextResponse.json({
      duplicate: true,
      cccd_trung: Boolean(json.cccd_trung),
      matches: json.matches ?? [],
    });
  }
  if (!res.ok) {
    const msg =
      json.message || json.detail || json.error || "Không tạo được bệnh nhân.";
    return NextResponse.json({ error: msg }, { status: res.status });
  }

  // The patient.created event is written by FastAPI inside the same
  // transaction as the row. It used to be written here afterwards with the
  // service-role key, which meant a crash in between left a patient with no
  // audit trail — and it was the last write in the dashboard that bypassed RLS.
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
  /** Mốc `updated_at` màn hình đã đọc — thẻ khoá lạc quan. Xem chỗ chuyển tiếp. */
  sua_luc?: string;
  full_name?: string;
  date_of_birth?: string | null;
  phone_primary?: string | null;
  phone_secondary?: string | null;
  national_id_number?: string | null;
  email?: string | null;
  location_id?: string;
  gender?: string | null;
  ethnicity?: string | null;
  nationality?: string | null;
  occupation?: string | null;
  patient_objection?: string | null;
  address?: string | null;
  guardian_name?: string | null;
}

export async function PATCH(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  // SỬA hồ sơ hành chính: backend quyết ai sửa được (`_PATIENT_EDIT_GUARD`) —
  // proxy chỉ kiểm đăng nhập (kiểm toán 27/09/2026).

  let body: PatchBody;
  try {
    body = (await request.json()) as PatchBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.clinic_patient_id ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id bệnh nhân." }, { status: 400 });

  if (body.full_name !== undefined) {
    const full_name = (body.full_name ?? "").trim();
    const loiTenSua = tenError(full_name);
    if (loiTenSua) {
      return NextResponse.json({ error: loiTenSua }, { status: 400 });
    }
  }

  // SỬA cũng phải qua đúng luật như TẠO. Chỉ kiểm khi trường có gửi lên.
  if (body.date_of_birth !== undefined) {
    const loiNgaySinhSua = dobErrorIso(body.date_of_birth, homNayVn());
    if (loiNgaySinhSua) {
      return NextResponse.json({ error: loiNgaySinhSua }, { status: 400 });
    }
  }

  // Quy tắc nhập liệu CỨNG (server-side): SĐT 10 số.
  if (body.phone_primary !== undefined) {
    const editPhone = (body.phone_primary ?? "").trim();
    if (editPhone && !PHONE_RE.test(editPhone)) {
      return NextResponse.json(
        { error: "SĐT chính không hợp lệ (10 số, bắt đầu bằng 0; đầu số 03/05/07/08/09)." },
        { status: 400 },
      );
    }
  }
  if (body.phone_secondary !== undefined) {
    const editPhone2 = (body.phone_secondary ?? "").trim();
    if (editPhone2 && !PHONE_RE.test(editPhone2)) {
      return NextResponse.json(
        { error: "SĐT người nhà không hợp lệ (10 số, bắt đầu bằng 0; đầu số 03/05/07/08/09)." },
        { status: 400 },
      );
    }
  }

  if (body.national_id_number !== undefined) {
    const editCccd = (body.national_id_number ?? "").trim();
    if (editCccd && !/^(\d{9}|\d{12})$/.test(editCccd)) {
      return NextResponse.json(
        { error: "Số CCCD phải gồm 9 hoặc 12 chữ số." },
        { status: 422 },
      );
    }
  }

  // W5 (ADR-0012): PATCH /api/v1/patients/{id} owns this now. It is scoped to
  // the caller's clinic — this path updated by clinic_patient_id alone, which
  // reaches every clinic once there is more than one. Off until
  // PATIENT_EDIT_VIA_BACKEND=1.
  const backendPayload: Record<string, unknown> = {};
  if (body.full_name !== undefined) backendPayload.full_name = (body.full_name ?? "").trim() || null;
  if (body.date_of_birth !== undefined) backendPayload.date_of_birth = (body.date_of_birth ?? "").trim() || null;
  if (body.phone_primary !== undefined) backendPayload.phone_primary = (body.phone_primary ?? "").trim() || null;
  if (body.phone_secondary !== undefined) backendPayload.phone_secondary = (body.phone_secondary ?? "").trim() || null;
  if (body.national_id_number !== undefined) backendPayload.national_id_number = (body.national_id_number ?? "").trim() || null;
  if (body.email !== undefined) backendPayload.email = (body.email ?? "").trim() || null;
  if (body.gender !== undefined) backendPayload.gender = nn(body.gender);
  if (body.ethnicity !== undefined) backendPayload.ethnicity = nn(body.ethnicity);
  if (body.nationality !== undefined) backendPayload.nationality = nn(body.nationality);
  if (body.occupation !== undefined) backendPayload.occupation = nn(body.occupation);
  if (body.patient_objection !== undefined) backendPayload.patient_objection = nn(body.patient_objection);
  if (body.address !== undefined) backendPayload.address = nn(body.address);
  if (body.guardian_name !== undefined) backendPayload.guardian_name = nn(body.guardian_name);
  if ((body.location_id ?? "").trim()) backendPayload.location_id = (body.location_id ?? "").trim();
  if ((body.sua_luc ?? "").trim()) backendPayload.sua_luc = (body.sua_luc ?? "").trim();

  return proxyJsonToBackend("PATCH", `/api/v1/patients/${id}`, backendPayload);
}
