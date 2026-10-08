// Lịch sử bàn giao thuốc — đọc qua backend `GET /api/v1/pharmacy/lich-su`
// (24/09/2026; trước đọc thẳng `prescription` bằng Supabase). Kèm ba con số của
// một dòng: bác sĩ kê · khách mua · đã giao.

import { fetchFromBackend } from "../../../../lib/backend-proxy";
import { requireNavAccess } from "../../../../lib/clinic-session";
import HistoryBoard from "./HistoryBoard";

export const dynamic = "force-dynamic";

interface DongLichSu {
  id: string;
  source_ref: string | null;
  drug_name_raw: string | null;
  /** Thuốc kho quầy đã chọn — thuốc THẬT đã giao (08/10/2026). */
  ten_thuoc_kho: string | null;
  dosage_instructions: string | null;
  quantity: string | null;
  quantity_note: string | null;
  quantity_num: number | null;
  purchased_qty: number | null;
  dispensed_qty: number | null;
  unit: string | null;
  dispensed_at: string | null;
  created_at: string | null;
  full_name: string | null;
  phone_primary: string | null;
}

export default async function PharmacyHistoryPage() {
  await requireNavAccess("/pharmacy/history");
  const data = await fetchFromBackend<{ items: DongLichSu[] }>("/api/v1/pharmacy/lich-su");
  if (!data) {
    return (
      <div className="p-6 text-sm text-danger">
        Không đọc được lịch sử (máy chủ không trả lời hoặc tài khoản không có quyền xem nhà
        thuốc).
      </div>
    );
  }
  const records = data.items.map(({ full_name, phone_primary, ...r }) => ({
    ...r,
    patient: { full_name, phone_primary },
  }));
  return <HistoryBoard records={records} />;
}
