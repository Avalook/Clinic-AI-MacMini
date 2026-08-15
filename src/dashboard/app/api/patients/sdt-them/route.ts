// POST /api/patients/sdt-them — gắn thêm một số điện thoại vào hồ sơ CÓ SẴN.
//
// Lối thứ ba của ô cảnh báo trùng ở màn tạo bệnh nhân (Tuyền 15/08/2026):
// "đúng là khách cũ, thêm số cho họ" — thay vì chỉ hai lối "vẫn tạo mới"
// (tách đôi bệnh án) và "bỏ dở". Toàn bộ luật (chuẩn hoá số, chặn trùng
// trong chính hồ sơ, ghi event_log) nằm ở FastAPI — đây là cửa chuyển tiếp
// có gác vai, và dùng proxyJsonToBackend để câu từ chối của backend ("Số này
// đã nằm trên hồ sơ của chính khách rồi") NỔI LÊN nguyên văn cho người trực
// đọc, không bị nuốt thành một mã lỗi câm.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getClinicRole } from "../../../../lib/clinic-session";
import { canWriteIntake } from "../../../../lib/roles";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function POST(request: Request) {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Chưa đăng nhập." }, { status: 401 });
  }
  // Cùng vai với màn tạo bệnh nhân — nơi duy nhất có nút này.
  const role = await getClinicRole();
  if (!canWriteIntake(role)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const body = (await request.json().catch(() => null)) as {
    clinic_patient_id?: string;
    so_dien_thoai?: string;
    loai?: string;
  } | null;
  if (!body?.clinic_patient_id || !body.so_dien_thoai?.trim()) {
    return NextResponse.json(
      { error: "Thiếu khách hoặc thiếu số điện thoại." },
      { status: 422 },
    );
  }

  return proxyJsonToBackend("POST", "/api/v1/patients/sdt-them", {
    clinic_patient_id: body.clinic_patient_id,
    so_dien_thoai: body.so_dien_thoai.trim(),
    loai: body.loai === "NGUOI_NHA" ? "NGUOI_NHA" : "CHINH",
  });
}

// DELETE — gỡ một số thêm. Cùng cửa, cùng gác vai: xoá số là sửa hồ sơ.
export async function DELETE(request: Request) {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Chưa đăng nhập." }, { status: 401 });
  }
  const role = await getClinicRole();
  if (!canWriteIntake(role)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const sp = new URL(request.url).searchParams;
  const benhNhan = sp.get("clinic_patient_id")?.trim();
  const so = sp.get("so_dien_thoai")?.trim();
  if (!benhNhan || !so) {
    return NextResponse.json(
      { error: "Thiếu khách hoặc thiếu số điện thoại." },
      { status: 422 },
    );
  }
  const qs = new URLSearchParams({ clinic_patient_id: benhNhan, so_dien_thoai: so });
  return proxyJsonToBackend("DELETE", `/api/v1/patients/sdt-them?${qs}`, null);
}
