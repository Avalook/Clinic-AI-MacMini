// Nhà thuốc — Kho & tồn kho (image_9 phần kho).
// Dược sĩ xem tồn theo lô/hạn dùng, nhập lô mới, điều chỉnh tồn.

import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getClinicRole, requireNavAccess } from "../../../../lib/clinic-session";
import { canWriteInventory } from "../../../../lib/roles";
import InventoryBoard from "./InventoryBoard";

export const dynamic = "force-dynamic";

export default async function PharmacyInventoryPage() {
  await requireNavAccess("/pharmacy/inventory");
  const canWrite = canWriteInventory(await getClinicRole());
  const supabase = await getSupabaseServer();

  const { data: batches, error } = await supabase
    .from("drug_batch")
    .select(
      `id, batch_code, expiry_date, quantity_on_hand, unit, cost_price, received_at,
       drug:drug_catalog_id(name_base, name_raw, variant)`,
    )
    .order("expiry_date", { ascending: true });

  // Danh mục thuốc cho ô chọn khi nhập/xuất. Chỉ nạp khi người này ghi được:
  // không có nút nào dùng tới nó thì một câu query nữa là phí.
  const { data: drugRows } = canWrite
    ? await supabase
        .from("drug_catalog")
        .select("id, name_base, name_raw, variant")
        .eq("is_active", true)
        .order("name_base", { ascending: true })
    : { data: [] };

  if (error) {
    return (
      <div className="p-6 text-sm text-danger">
        Không đọc được kho: {error.message}
      </div>
    );
  }

  interface BatchDrugRaw {
    name_base: string | null;
    name_raw: string | null;
    variant: string | null;
  }
  type BatchRaw = Omit<(typeof batches)[number], "drug"> & {
    drug: BatchDrugRaw[] | null;
  };
  const normalized = (batches ?? []).map((b: BatchRaw) => ({
    ...b,
    drug: b.drug?.[0] ?? null,
  }));

  const drugs = (drugRows ?? []).map((d) => ({
    id: d.id,
    label: `${d.name_base ?? d.name_raw ?? "—"}${d.variant ? ` (${d.variant})` : ""}`,
  }));

  return (
    <InventoryBoard batches={normalized} drugs={drugs} canWrite={canWrite} />
  );
}