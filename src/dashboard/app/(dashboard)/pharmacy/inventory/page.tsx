// Nhà thuốc — Kho & tồn kho (image_9 phần kho).
// Dược sĩ xem tồn theo lô/hạn dùng, nhập lô mới, điều chỉnh tồn.

import { getSupabaseServer } from "../../../../lib/supabase-server";
import { motBanGhi } from "../../../../lib/postgrest-embed";
import { requireNavAccess } from "../../../../lib/clinic-session";
import InventoryBoard from "./InventoryBoard";

export const dynamic = "force-dynamic";

export default async function PharmacyInventoryPage() {
  await requireNavAccess("/pharmacy/inventory");
  const supabase = await getSupabaseServer();

  const { data: batches, error } = await supabase
    .from("drug_batch")
    .select(
      `id, batch_code, expiry_date, quantity_on_hand, unit, cost_price, received_at,
       drug:drug_catalog_id(name_base, name_raw, variant)`,
    )
    .order("expiry_date", { ascending: true });

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
    drug: motBanGhi(b.drug),
  }));

  return <InventoryBoard batches={normalized} />;
}