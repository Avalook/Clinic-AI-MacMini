// Trang lẻ "SỐ THỨ TỰ GỌI KHÁM" — bảng số thứ tự ưu tiên (Model ②).
//   • Số vé (queue_number) = ĐỊNH DANH cấp lúc đến, KHÔNG phải thứ tự gọi.
//   • Thứ tự GỌI tính theo callRank(): ƯT (người quen) → có hẹn đến đúng giờ
//     (≤ giờ hẹn + 10') → walk-in / đến trễ theo GIỜ ĐẾN. Gọi bệnh nhân theo TÊN.
// Chỉ đọc (RLS SELECT). Tự làm mới mỗi 30s ở client để bảng luôn cập nhật.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess } from "../../../lib/clinic-session";
import { vnTodayRangeUtc } from "../../../lib/datetime";
import QueueBoard, { type QueueRow } from "./QueueBoard";
import { b3ReadyApptIds, type LabLite } from "../../../lib/queue";

export const dynamic = "force-dynamic";

// Lấy lịch HÔM NAY đang trong hàng khám (đã check-in, chưa khám xong) + mốc giờ
// đến thật (visit.checked_in_at) + kênh đặt để tính ưu tiên. visit là 1-nhiều khi
// embed từ phía appointment ⇒ PostgREST trả MẢNG; phẳng hoá ở dưới.
const SELECT = `
  id, slot_start, status, queue_number, booking_channel,
  patient:patient!clinic_patient_id ( full_name, patient_code ),
  doctor:staff!doctor_id ( full_name ),
  service:service_type!service_type_id ( name ),
  visit:visit!appointment_id ( checked_in_at, status )
`;

type RawRow = Omit<QueueRow, "checked_in_at" | "visit_status"> & {
  visit?: { checked_in_at: string | null; status: string | null }[] | null;
};

export default async function QueuePage() {
  await requireNavAccess("/queue");
  const supabase = await getSupabaseServer();
  const { startUtc: dayStart, endUtc: dayEnd } = vnTodayRangeUtc();

  // CHECKED_IN = đang chờ gọi / đang khám (thành COMPLETED khi bác sĩ khám xong).
  const { data, error } = await supabase
    .from("appointment")
    .select(SELECT)
    .gte("slot_start", dayStart)
    .lt("slot_start", dayEnd)
    .eq("status", "CHECKED_IN")
    .order("slot_start", { ascending: true })
    .limit(300);

  const appts = (data as RawRow[] | null) ?? [];
  // Làn "Chờ đọc KQ (B3)" (T-QUEUE-B3): lượt nào đã có KQ lab về hết → kéo lên đầu cho
  // bác sĩ đọc nhanh. Match theo appointment_id (lab-result API set sạch). Best-effort.
  let readySet = new Set<string>();
  const apptIds = appts.map((r) => r.id);
  if (apptIds.length > 0) {
    const { data: labs } = await supabase
      .from("lab_result")
      .select("appointment_id, result_value, external_ref")
      .in("appointment_id", apptIds);
    readySet = b3ReadyApptIds((labs as LabLite[] | null) ?? []);
  }

  const rows: QueueRow[] = appts.map((r) => {
    const v = r.visit?.[0] ?? null;
    return {
      id: r.id,
      slot_start: r.slot_start,
      status: r.status,
      queue_number: r.queue_number,
      booking_channel: r.booking_channel ?? null,
      patient: r.patient,
      doctor: r.doctor,
      service: r.service,
      checked_in_at: v?.checked_in_at ?? null,
      visit_status: v?.status ?? null,
      b3_ready: readySet.has(r.id),
    };
  });

  return <QueueBoard rows={rows} error={error?.message ?? null} />;
}
