// Nhà thuốc — Đơn thuốc chờ cấp + Chuẩn bị thuốc (image_8 + image_9).
// Dược sĩ (PHARMACIST) quản lý hàng đợi đơn thuốc, soạn thuốc theo đơn,
// kiểm tra trước bàn giao. Kho đầy đủ (lô/hạn dùng) qua drug_batch + inventory_txn.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess } from "../../../lib/clinic-session";
import PharmacyBoard from "./PharmacyBoard";

export const dynamic = "force-dynamic";

export default async function PharmacyPage() {
  await requireNavAccess("/pharmacy");
  const supabase = await getSupabaseServer();

  // Đơn thuốc CÒN VIỆC (prescription) + bệnh nhân + lượt khám
  // HAI TRUY VẤN NÀY KHÔNG LIÊN QUAN GÌ NHAU — đơn thuốc hôm nay và tồn kho.
  // Xếp hàng chúng là cộng thêm một lượt ~210ms sang Seoul mà không đổi kết
  // quả. Bắn cùng lúc, chờ một lần.
  const qRx = supabase
    .from("prescription")
    .select(
      `id, source_ref, drug_name_raw, dosage_instructions, quantity, quantity_note,
       quantity_num, unit, dispensed_qty, dispense_status, closed_at,
       created_at,
       patient:clinic_patient_id(full_name, phone_primary),
       visit:visit_id(visit_id)`,
    )
    // KHÔNG lọc theo NGÀY. Bản trước chỉ lấy đơn tạo hôm nay, nên một đơn kê
    // chiều qua mà khách sáng nay mới tới lấy thì biến mất khỏi hàng đợi —
    // dược sĩ không có đường nào cấp nốt. Lọc theo VIỆC CÒN LẠI: chưa chốt.
    .is("closed_at", null)
    .order("created_at", { ascending: false })
    .limit(200);

  const qInv = supabase
    .from("drug_batch")
    .select(
      `id, batch_code, expiry_date, quantity_on_hand, unit, cost_price,
       drug:drug_catalog_id(name_base, name_raw, variant)`,
    )
    .gt("quantity_on_hand", 0)
    .order("expiry_date", { ascending: true });

  // Tồn kho theo thuốc (drug_catalog + drug_batch)
  const [
    { data: prescriptions, error: rxErr },
    { data: inventory, error: invErr },
  ] = await Promise.all([qRx, qInv]);

  if (rxErr) {
    return (
      <div className="p-6 text-sm text-danger">
        Không đọc được đơn thuốc: {rxErr.message}
      </div>
    );
  }

  // Supabase trả FK relationship dạng mảng — chuẩn hoá về object|null.
  interface RxPatientRaw {
    full_name: string | null;
    phone_primary: string | null;
  }
  interface RxVisitRaw {
    visit_id: string;
  }
  type RxRaw = Omit<
    (typeof prescriptions)[number],
    "patient" | "visit"
  > & {
    patient: RxPatientRaw[] | null;
    visit: RxVisitRaw[] | null;
  };
  const normalizedRxs = (prescriptions ?? []).map((p: RxRaw) => ({
    ...p,
    patient: p.patient?.[0] ?? null,
    visit: p.visit?.[0] ?? null,
  }));



  if (invErr) {
    return (
      <div className="p-6 text-sm text-danger">
        Không đọc được tồn kho: {invErr.message}
      </div>
    );
  }

  interface BatchDrugRaw {
    name_base: string | null;
    name_raw: string | null;
    variant: string | null;
  }
  type BatchRaw = Omit<(typeof inventory)[number], "drug"> & {
    drug: BatchDrugRaw[] | null;
  };
  const normalizedInv = (inventory ?? []).map((b: BatchRaw) => ({
    ...b,
    drug: b.drug?.[0] ?? null,
  }));

  return (
    <PharmacyBoard
      prescriptions={normalizedRxs}
      inventory={normalizedInv}
    />
  );
}
