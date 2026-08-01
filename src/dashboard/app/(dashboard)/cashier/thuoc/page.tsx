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
    <main className="page-in space-y-4 p-4 lg:p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Bảng giá thuốc</h1>
          <p className="text-sm text-ink-muted">
            Quản lý mã thuốc, đơn giá và trạng thái áp dụng tại quầy thu ngân.
          </p>
        </div>
        <span className="rounded-control border border-line bg-surface px-3 py-1.5 text-xs text-ink-muted">
          Danh mục nhà thuốc
        </span>
      </header>

      {error ? (
        <div className="rounded-control border border-danger bg-danger-bg px-3 py-2.5 text-sm text-danger">
          Không tải được bảng giá thuốc. Vui lòng thử lại sau.
        </div>
      ) : (
        <CashierView rows={rows} group="thuoc" />
      )}
    </main>
  );
}
