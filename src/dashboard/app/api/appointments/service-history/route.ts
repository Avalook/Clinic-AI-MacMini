// GET /api/appointments/service-history?clinic_patient_id=...&service_type_id=...
// Cấp dữ liệu cho chú thích đặt lịch BN cũ (T-20260629-EPI-01): BN này đã khám DỊCH VỤ
// này bao nhiêu lần + có đợt khám nào còn SỐNG không. Frontend dùng để (a) hiện hint, (b)
// đặt mặc định thông minh NEW/RETURN. Chỉ đọc.
//
// 24/09/2026: đọc qua backend `GET /api/v1/appointments/lich-su-dich-vu` thay vì
// đọc thẳng `appointment` / `care_episode` bằng Supabase.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";
import { getSupabaseServer } from "../../../../lib/supabase-server";

export async function GET(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const { searchParams } = new URL(request.url);
  const clinic_patient_id = (searchParams.get("clinic_patient_id") ?? "").trim();
  const service_type_id = (searchParams.get("service_type_id") ?? "").trim();
  if (!clinic_patient_id || !service_type_id) {
    return NextResponse.json(
      { error: "Thiếu clinic_patient_id / service_type_id." },
      { status: 400 },
    );
  }
  const q = new URLSearchParams({ clinic_patient_id, service_type_id });
  return proxyJsonToBackend(
    "GET",
    `/api/v1/appointments/lich-su-dich-vu?${q.toString()}`,
    undefined,
  );
}
