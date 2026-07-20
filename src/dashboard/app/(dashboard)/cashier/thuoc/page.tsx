// Bảng giá THUỐC (group=thuoc) — tách từ trang gộp cũ (T-DASH-CASHIER-IA-02).
// Tái dùng scaffold CashierView (khoá group="thuoc" → ẩn toggle). Đọc qua RLS,
// ghi qua /api/service-price (POST đã nhận group). Lọc group ngay ở query.

import { getSupabaseServer } from "../../../../lib/supabase-server";
import { requireNavAccess } from "../../../../lib/clinic-session";
import CashierView, { type PriceRow } from "../CashierView";

export const dynamic = "force-dynamic";

export default async function PriceThuocPage() {
  await requireNavAccess("/cashier/thuoc");
  const supabase = await getSupabaseServer();

  const { data, error } = await supabase
    .from("service_price")
    .select("id, service_code, name, group, unit_price, active")
    .eq("group", "thuoc")
    .order("service_code", { ascending: true })
    .limit(1000);

  const rows = (data as PriceRow[] | null) ?? [];

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold text-[#171717]">Bảng giá thuốc</h1>
        <p className="text-sm text-[#888888]">
          Danh mục giá thuốc. Đơn giá để trống = chưa chốt giá (nhập sau).
        </p>
      </header>

      {error ? (
        <div className="rounded-md bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">
          {error.message}
        </div>
      ) : (
        <CashierView rows={rows} group="thuoc" />
      )}
    </div>
  );
}
