// GET /api/appointments/service-history?clinic_patient_id=...&service_type_id=...
// Cấp dữ liệu cho chú thích đặt lịch BN cũ (T-20260629-EPI-01): BN này đã khám DỊCH VỤ
// này bao nhiêu lần + có đợt khám nào còn SỐNG không. Frontend dùng để (a) hiện hint, (b)
// đặt mặc định thông minh NEW/RETURN. Chỉ đọc.
import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getSupabaseService } from "../../../../lib/supabase-service";

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

  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }

  // Số lượt đã đặt cho dịch vụ này (bỏ huỷ / không đến) — chỉ cần đếm.
  const { count: serviceVisitCount } = await db
    .from("appointment")
    .select("id", { count: "exact", head: true })
    .eq("clinic_patient_id", clinic_patient_id)
    .eq("service_type_id", service_type_id)
    .not("status", "eq", "CANCELLED")
    .not("status", "eq", "NO_SHOW");

  // Đợt còn SỐNG (OPEN / PENDING_CLOSE) cho (BN, dịch vụ) — partial unique ⇒ ≤ 1.
  // Bảng care_episode có thể CHƯA migrate trên DB này → bắt lỗi, coi như không có đợt.
  let liveEpisode: {
    id: string;
    status: string;
    opened_at: string;
    last_visit_at: string | null;
  } | null = null;
  try {
    const { data } = await db
      .from("care_episode")
      .select("id, status, opened_at, last_visit_at")
      .eq("clinic_patient_id", clinic_patient_id)
      .eq("service_type_id", service_type_id)
      .neq("status", "CLOSED")
      .limit(1)
      .maybeSingle();
    liveEpisode =
      (data as {
        id: string;
        status: string;
        opened_at: string;
        last_visit_at: string | null;
      } | null) ?? null;
  } catch {
    liveEpisode = null;
  }

  return NextResponse.json({
    serviceVisitCount: serviceVisitCount ?? 0,
    liveEpisode,
  });
}
