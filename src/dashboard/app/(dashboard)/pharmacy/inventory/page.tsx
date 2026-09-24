// Kho thuốc — tồn theo lô. Đọc qua backend `GET /api/v1/pharmacy/inventory`
// (24/09/2026; trước đọc thẳng `drug_batch` bằng Supabase).

import { fetchFromBackend } from "../../../../lib/backend-proxy";
import { requireNavAccess } from "../../../../lib/clinic-session";
import InventoryBoard from "./InventoryBoard";

export const dynamic = "force-dynamic";

interface LoTon {
  id: string;
  name_base: string | null;
  variant: string | null;
  // Bốn cột NOT NULL ở `drug_batch` (xem PharmacyService.nhap_lo).
  batch_code: string;
  expiry_date: string;
  quantity_on_hand: number;
  unit: string;
  cost_price: number | null;
  received_at: string | null;
}

export default async function PharmacyInventoryPage() {
  await requireNavAccess("/pharmacy/inventory");
  const data = await fetchFromBackend<{ items: LoTon[] }>("/api/v1/pharmacy/inventory");
  if (!data) {
    return (
      <div className="p-6 text-sm text-danger">
        Không đọc được kho (máy chủ không trả lời hoặc tài khoản chưa có quyền xem nhà
        thuốc).
      </div>
    );
  }
  const batches = [...data.items]
    .sort((a, b) => a.expiry_date.localeCompare(b.expiry_date))
    .map(({ name_base, variant, ...b }) => ({
      ...b,
      drug: { name_base, name_raw: name_base, variant },
    }));
  return <InventoryBoard batches={batches} />;
}
