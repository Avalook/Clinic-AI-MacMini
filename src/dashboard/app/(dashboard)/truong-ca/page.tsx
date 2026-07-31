// "Theo dõi buổi" của TRƯỞNG CA — READ-ONLY. Hiển thị các buổi khám (visit) TẠO
// HÔM NAY: giờ vào · bệnh nhân · bác sĩ · dịch vụ · trạng thái. CHỈ ĐỌC, không
// nút mutate (Trưởng ca = vai HÀNH CHÍNH, KHÔNG ghi lâm sàng). Tái dùng
// VisitStatusBoard (đang dùng cho Lễ tân ở trang chủ) + đọc qua RLS SELECT.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess } from "../../../lib/clinic-session";
import { vnTodayRangeUtc } from "../../../lib/datetime";
import VisitStatusBoard, { type VisitStatusRow } from "../home/VisitStatusBoard";

export const dynamic = "force-dynamic";

// 3 staff-FK trên visit → chỉ rõ attending_doctor_id để PostgREST không nhập nhằng.
const VISIT_STATUS_SELECT = `
  visit_id, status, checked_in_at, created_at,
  patient:patient!clinic_patient_id ( full_name, patient_code ),
  doctor:staff!attending_doctor_id ( full_name ),
  service:service_type!service_type_id ( name ),
  appointment:appointment!appointment_id ( status )
`;

export default async function TruongCaPage() {
  await requireNavAccess("/truong-ca");
  const supabase = await getSupabaseServer();
  const { startUtc, endUtc } = vnTodayRangeUtc();

  const { data, error } = await supabase
    .from("visit")
    .select(VISIT_STATUS_SELECT)
    .gte("created_at", startUtc)
    .lt("created_at", endUtc)
    .order("created_at", { ascending: true })
    .limit(300);

  const rows = (data as VisitStatusRow[] | null) ?? [];

  // Mốc "Đã thanh toán": đã thu đủ DỊCH VỤ + THUỐC (nếu có đơn). Đọc payment +
  // prescription. Bảng payment có thể chưa tồn tại (migration 056) → bỏ qua.
  if (rows.length) {
    const vids = rows.map((v) => v.visit_id);
    const [payRes, rxRes] = await Promise.all([
      supabase.from("payment").select("visit_id, kind").in("visit_id", vids),
      supabase.from("prescription").select("visit_id").in("visit_id", vids),
    ]);
    const paidKinds = new Map<string, Set<string>>();
    for (const p of (payRes.data as { visit_id: string; kind: string }[] | null) ?? []) {
      const s = paidKinds.get(p.visit_id) ?? new Set<string>();
      s.add(p.kind);
      paidKinds.set(p.visit_id, s);
    }
    const hasRx = new Set(
      ((rxRes.data as { visit_id: string }[] | null) ?? []).map((r) => r.visit_id),
    );
    for (const v of rows) {
      const kinds = paidKinds.get(v.visit_id) ?? new Set<string>();
      const needsThuoc = hasRx.has(v.visit_id);
      v.paid = kinds.has("dich_vu") && (!needsThuoc || kinds.has("thuoc"));
    }
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold text-ink">Theo dõi buổi</h1>
        <p className="text-sm text-ink-muted">
          Trạng thái các buổi khám hôm nay (chỉ xem). Trưởng ca theo dõi luồng —
          không chỉnh sửa hồ sơ lâm sàng.
        </p>
      </header>

      {error ? (
        <div className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
          {error.message}
        </div>
      ) : (
        <VisitStatusBoard rows={rows} />
      )}
    </div>
  );
}
