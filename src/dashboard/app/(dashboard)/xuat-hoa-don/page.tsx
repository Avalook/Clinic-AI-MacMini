import { requireNavAccess } from "@/lib/clinic-session";
import { layCoSo } from "@/lib/danh-muc";
import XuatHoaDon from "./XuatHoaDon";

export const dynamic = "force-dynamic";
export const metadata = { title: "Xuất hoá đơn" };

export default async function TrangXuatHoaDon() {
  await requireNavAccess("/xuat-hoa-don");
  const coSo = await layCoSo();
  return <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
    <header className="space-y-1">
      <h1 className="text-title font-semibold text-ink">Xuất hoá đơn</h1>
      <p className="text-body text-ink-muted">File Excel đúng mẫu nhập hoá đơn GTGT của kế toán. Ô hệ thống chưa có dữ liệu (mã số thuế, thuế suất…) để trống.</p>
    </header>
    <XuatHoaDon coSo={coSo} />
  </main>;
}
