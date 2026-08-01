// "Theo dõi buổi" của TRƯỞNG CA — READ-ONLY. Hiển thị các buổi khám (visit) TẠO
// HÔM NAY: giờ vào · bệnh nhân · bác sĩ · dịch vụ · trạng thái. CHỈ ĐỌC, không
// nút mutate (Trưởng ca = vai HÀNH CHÍNH, KHÔNG ghi lâm sàng). Tái dùng
// VisitStatusBoard (đang dùng cho Lễ tân ở trang chủ) + đọc qua RLS SELECT.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess } from "../../../lib/clinic-session";
import { vnTodayRangeUtc } from "../../../lib/datetime";
import StatCard from "../../../components/ui/StatCard";
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

  const baseRows = (data as VisitStatusRow[] | null) ?? [];
  let rows = baseRows;
  let paymentDataAvailable = error == null;

  // Mốc "Đã thanh toán": đã thu đủ DỊCH VỤ + THUỐC (nếu có đơn). Đọc payment +
  // prescription. Bảng payment có thể chưa tồn tại (migration 056) → bỏ qua.
  if (baseRows.length) {
    const vids = baseRows.map((v) => v.visit_id);
    const [payRes, rxRes] = await Promise.all([
      supabase.from("payment").select("visit_id, kind").in("visit_id", vids),
      supabase.from("prescription").select("visit_id").in("visit_id", vids),
    ]);
    paymentDataAvailable = payRes.error == null && rxRes.error == null;
    const paidKinds = new Map<string, Set<string>>();
    for (const p of (payRes.data as { visit_id: string; kind: string }[] | null) ?? []) {
      const s = paidKinds.get(p.visit_id) ?? new Set<string>();
      s.add(p.kind);
      paidKinds.set(p.visit_id, s);
    }
    const hasRx = new Set(
      ((rxRes.data as { visit_id: string }[] | null) ?? []).map((r) => r.visit_id),
    );
    if (paymentDataAvailable) {
      rows = baseRows.map((visit) => {
        const kinds = paidKinds.get(visit.visit_id) ?? new Set<string>();
        const needsThuoc = hasRx.has(visit.visit_id);
        return {
          ...visit,
          paid: kinds.has("dich_vu") && (!needsThuoc || kinds.has("thuoc")),
        };
      });
    }
  }

  const received = error
    ? "—"
    : rows.filter((visit) => visit.checked_in_at != null).length;
  const paid = paymentDataAvailable
    ? rows.filter((visit) => visit.paid === true).length
    : "—";
  const needsAttention = paymentDataAvailable
    ? rows.filter(
        (visit) => visit.checked_in_at != null && visit.paid !== true,
      ).length
    : "—";

  return (
    <main className="page-in min-w-0 space-y-5 p-4 lg:p-5">
      <header>
        <h1 className="text-xl font-semibold text-ink lg:text-2xl">
          Điều phối lượt khám — Trưởng ca
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          Giám sát luồng khám hôm nay bằng dữ liệu lượt khám thực tế. Màn hình
          chỉ đọc, không chỉnh sửa hồ sơ lâm sàng.
        </p>
      </header>

      <section aria-label="Tổng quan điều phối">
        <div className="grid min-w-0 grid-cols-1 divide-y divide-line rounded-card border border-line bg-surface shadow-card sm:grid-cols-2 sm:divide-y-0 xl:grid-cols-4">
          <StatCard label="Lượt khám hôm nay" value={error ? "—" : rows.length} tone="brand" />
          <StatCard label="Đã tiếp nhận" value={received} tone="neutral" />
          <StatCard label="Đã thanh toán" value={paid} tone="success" />
          <StatCard label="Cần theo dõi" value={needsAttention} tone="neutral" />
        </div>
        <p className="mt-2 text-xs text-ink-faint">
          {paymentDataAvailable
            ? "“Cần theo dõi” là lượt đã tiếp nhận nhưng chưa ghi nhận thanh toán đủ; đây không phải cảnh báo SLA."
            : "Chưa đọc đủ dữ liệu thanh toán và đơn thuốc; các KPI liên quan được để trống thay vì giả định bằng 0."}
        </p>
      </section>

      {error ? (
        <div className="rounded-card border border-danger bg-danger-bg px-4 py-3 text-sm text-danger">
          {error.message}
        </div>
      ) : !paymentDataAvailable ? (
        <div className="rounded-card border border-warning bg-warning-bg px-4 py-5 text-sm text-warning shadow-card">
          <p className="font-medium">Chưa thể hiển thị trạng thái hành trình</p>
          <p className="mt-1 text-xs leading-5">
            Nguồn thanh toán hoặc đơn thuốc chưa phản hồi. Danh sách được tạm ẩn
            để không gắn nhầm lượt khám là “chờ thu”.
          </p>
        </div>
      ) : (
        <section className="min-w-0" aria-label="Danh sách lượt khám">
          <div className="mb-3 flex items-baseline justify-between gap-3">
            <h2 className="font-semibold text-ink">Danh sách lượt khám</h2>
            <span className="text-xs text-ink-muted">{rows.length} lượt</span>
          </div>
          <VisitStatusBoard rows={rows} />
        </section>
      )}
    </main>
  );
}
