// Nhà thuốc — Lịch sử bàn giao thuốc (image_10).
// Tra cứu bản ghi thuốc đã cấp cho từng bệnh nhân (read-only, bất biến).

import { getSupabaseServer } from "../../../../lib/supabase-server";
import { requireNavAccess } from "../../../../lib/clinic-session";
import HistoryBoard from "./HistoryBoard";

export const dynamic = "force-dynamic";

export default async function PharmacyHistoryPage() {
  await requireNavAccess("/pharmacy/history");
  const supabase = await getSupabaseServer();

  const { data: records, error } = await supabase
    .from("prescription")
    .select(
      `id, source_ref, drug_name_raw, dosage_instructions, quantity, quantity_note,
       dispensed_qty, unit, dispense_status, dispensed_at, created_at,
       patient:clinic_patient_id(full_name, phone_primary)`,
    )
    // "LỊCH SỬ BÀN GIAO" PHẢI LÀ THUỐC ĐÃ RA KHỎI KHO.
    //
    // Bản trước đọc CẢ BẢNG prescription không lọc gì, nên nó liệt kê mọi đơn
    // bác sĩ vừa kê và gọi đó là "đã bàn giao". Không một thao tác bàn giao nào
    // từng xảy ra, mà người quản lý nhìn vào sẽ tin thuốc đã ra khỏi kho. Đó là
    // màn hình nói dối, không phải màn hình thiếu dữ liệu.
    .gt("dispensed_qty", 0)
    .order("dispensed_at", { ascending: false })
    .limit(200);

  if (error) {
    return (
      <div className="p-6 text-sm text-danger">
        Không đọc được lịch sử: {error.message}
      </div>
    );
  }

  interface PatientRaw {
    full_name: string | null;
    phone_primary: string | null;
  }
  type Raw = Omit<(typeof records)[number], "patient"> & {
    patient: PatientRaw[] | null;
  };
  const normalized = (records ?? []).map((r: Raw) => ({
    ...r,
    patient: r.patient?.[0] ?? null,
  }));

  return <HistoryBoard records={normalized} />;
}