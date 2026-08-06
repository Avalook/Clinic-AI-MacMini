// Bảng giá THUỐC (group=thuoc) — tách từ trang gộp cũ (T-DASH-CASHIER-IA-02).
// Tái dùng scaffold CashierView (khoá group="thuoc" → ẩn toggle). Đọc qua
// FastAPI, ghi qua /api/service-price. Lọc group ở MÁY CHỦ, không tải cả
// bảng giá về rồi lọc ở trình duyệt.

import { fetchFromBackend } from "../../../../lib/backend-proxy";
import { requireNavAccess } from "../../../../lib/clinic-session";
import CashierView, { type PriceRow } from "../CashierView";

export const dynamic = "force-dynamic";

export default async function PriceThuocPage() {
  await requireNavAccess("/cashier/thuoc");
  // Đọc qua FastAPI thay vì đọc thẳng bảng: đọc thẳng cần vai Postgres
  // (`authenticated`) mà database cho thuê không cho tạo. Phần GHI đã đi qua
  // /api/service-price từ trước — đây là nửa còn lại.
  const data = await fetchFromBackend<PriceRow[]>(
    "/api/v1/service-prices?group=thuoc",
  );
  // null = backend không trả lời. Bảng giá rỗng và bảng giá không đọc được
  // nhìn giống hệt nhau, mà một bên là "chưa khai giá" còn bên kia là "đừng
  // tin con số nào trên màn này".
  const error = data === null;
  const rows = data ?? [];

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
