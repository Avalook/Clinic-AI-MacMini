// Màn hình TV phòng chờ — hiển thị số đang gọi theo khu (image_15 + 2 ảnh V2).
// Public, không cần đăng nhập. Chỉ đọc appointment + queue_number hôm nay.

import { getSupabaseServer } from "../../lib/supabase-server";
import { vnTodayRangeUtc } from "../../lib/datetime";
import DisplayBoard from "./DisplayBoard";

export const dynamic = "force-dynamic";

export default async function DisplayPage() {
  const supabase = await getSupabaseServer();
  const { startUtc, endUtc } = vnTodayRangeUtc();

  // Lịch hôm nay có số thứ tự + trạng thái — nguồn cho bảng gọi số.
  const { data: appts, error } = await supabase
    .from("appointment")
    .select(
      // KHÔNG lấy tên bệnh nhân. Màn này treo ở phòng chờ và không cần đăng
      // nhập: bất cứ thứ gì select ở đây đều đi thẳng vào payload trình duyệt,
      // nên "không render" là chưa đủ — phải không tải về.
      `id, slot_start, status, queue_number, booking_channel,
       doctor:staff!doctor_id(full_name),
       service:service_type!service_type_id(name)`,
    )
    .gte("slot_start", startUtc)
    .lt("slot_start", endUtc)
    .not("status", "in", "(CANCELLED,NO_SHOW,DOCTOR_DECLINED)")
    .order("slot_start", { ascending: true })
    .limit(200);

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-ink text-white">
        <p className="text-lg">Không đọc được dữ liệu: {error.message}</p>
      </div>
    );
  }

  interface DoctorRaw {
    full_name: string | null;
  }
  interface ServiceRaw {
    name: string | null;
  }
  type Raw = Omit<(typeof appts)[number], "doctor" | "service"> & {
    doctor: DoctorRaw[] | null;
    service: ServiceRaw[] | null;
  };
  const normalized = (appts ?? []).map((a: Raw) => ({
    ...a,
    doctor: a.doctor?.[0] ?? null,
    service: a.service?.[0] ?? null,
  }));

  return <DisplayBoard appts={normalized} />;
}