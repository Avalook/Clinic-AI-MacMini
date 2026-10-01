// BẢNG GIÁ DỊCH VỤ & PHÒNG (group=dich_vu) — Tuyền 01/10/2026: mọi dịch vụ kèm
// nhóm hàng, giá, bên thu, nhóm việc và PHÒNG LÀM ĐƯỢC; lọc "Chưa có phòng",
// gán phòng tại chỗ. Đọc qua FastAPI (`/api/v1/service-prices/danh-muc` —
// máy chủ quyết phí khám / cần phòng / thiếu phòng), ghi qua /api/service-price
// và /api/clinic-config (service-rooms). Bảng giá thuốc vẫn ở CashierView.

import { fetchFromBackend } from "../../../../lib/backend-proxy";
import { requireNavAccess } from "../../../../lib/clinic-session";
import DanhMucDichVuPhong, { type DanhMucGoi } from "../DanhMucDichVuPhong";

export const dynamic = "force-dynamic";

export default async function PriceDichVuPage({
  searchParams,
}: {
  searchParams: Promise<{ loc?: string }>;
}) {
  await requireNavAccess("/cashier/dich-vu");
  const { loc } = await searchParams;
  // null = backend không trả lời — "không đọc được" khác "chưa có dịch vụ".
  const data = await fetchFromBackend<DanhMucGoi>("/api/v1/service-prices/danh-muc");

  return (
    <main className="page-in space-y-4 p-4 lg:p-5">
      <header>
        <h1 className="text-title font-semibold text-ink">Bảng giá dịch vụ &amp; phòng</h1>
        <p className="text-body text-ink-muted">
          Mọi dịch vụ phòng khám bán: nhóm hàng, đơn giá, bên thu và phòng làm được. Sửa là dùng
          ngay cho lượt mới — ô chỉ định của bác sĩ, quầy thu, xếp phòng cùng đọc danh mục này.
        </p>
      </header>
      <DanhMucDichVuPhong banDau={data} chiChuaPhong={loc === "chua-phong"} />
    </main>
  );
}
