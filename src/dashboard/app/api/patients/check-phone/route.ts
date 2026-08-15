// /api/patients/check-phone?phone=...
//   GET → cảnh báo SỚM nếu SĐT đã có hồ sơ (feedback #9). CHỈ ĐỌC, KHÔNG tạo,
//   KHÔNG chặn. Mẹ đăng ký bằng số của mình cho con là hợp lệ → để nhân viên
//   tự quyết; ta chỉ hiện trùng với ai.
//
// Tra THẲNG Supabase (giống guard trùng LÚC SUBMIT ở POST /api/patients) — KHÔNG
// qua FastAPI nữa: deploy không chắc reachable nên trước đây luôn trả rỗng →
// KHÔNG bao giờ cảnh báo. Trả TỐI THIỂU (tên + mã BN + năm sinh) — KHÔNG CCCD/địa chỉ.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getClinicRole } from "../../../../lib/clinic-session";
import { canWriteIntake } from "../../../../lib/roles";

const EMPTY = { exists: false, matches: [] as unknown[] };

interface PatientRow {
  clinic_patient_id: string;
  full_name: string | null;
  patient_code: string | null;
  date_of_birth: string | null;
}

export async function GET(request: Request) {
  // 1) Phải đăng nhập (cổng chung Supabase).
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Chưa đăng nhập." }, { status: 401 });
  }

  // 2) Chỉ vai ghi tiếp nhận (CSKH/Lễ tân/QL/ĐD) — đúng vai dùng màn tạo BN.
  const role = await getClinicRole();
  if (!canWriteIntake(role)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const phone = new URL(request.url).searchParams.get("phone")?.trim() ?? "";
  // Chỉ tra khi đủ 10 chữ số → tránh match nửa vời + tránh tra mỗi lần gõ.
  const digits = phone.replace(/\D/g, "");
  if (digits.length < 10) {
    return NextResponse.json(EMPTY);
  }
  const ten = digits.slice(-10); // chuẩn hoá: 10 số cuối (bỏ +84/84 nếu lỡ dán vào)

  // Đọc bằng session của người gọi. Không bypass RLS nữa (ADR-0012): từ
  // 20260730000004, `patient` lọc theo clinic_membership, nên cảnh báo trùng SĐT
  // chỉ soi trong phòng khám của chính người đang thao tác — đúng điều ta muốn.
  // `sdt_tim_kiem` gộp MỌI số của hồ sơ (chính + người nhà + số thêm —
  // migration 20260815000002): khách đăng ký bằng số phụ thì cảnh báo vẫn
  // phải nổ. `clinic_patient_id` để nút "thêm số cho khách này" biết gắn vào ai.
  const { data, error } = await supabase
    .from("patient")
    .select("clinic_patient_id, full_name, patient_code, date_of_birth")
    .ilike("sdt_tim_kiem", `%${ten}%`)
    .limit(5);
  if (error) {
    // Cảnh báo là tính năng PHỤ — lỗi tra thì im lặng, guard lúc submit vẫn chặn.
    return NextResponse.json(EMPTY);
  }

  const matches = ((data as PatientRow[] | null) ?? []).map((p) => ({
    clinic_patient_id: p.clinic_patient_id,
    full_name: p.full_name ?? "",
    patient_code: p.patient_code ?? "",
    birth_year: p.date_of_birth ? Number(String(p.date_of_birth).slice(0, 4)) || null : null,
  }));

  return NextResponse.json({ exists: matches.length > 0, matches });
}
