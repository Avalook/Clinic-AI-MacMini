import { requireNavAccess } from "@/lib/clinic-session";
import { layCoSo } from "@/lib/danh-muc";
import KeToan from "./KeToan";

export const dynamic = "force-dynamic";
export const metadata = { title: "Kế toán" };

export default async function TrangKeToan() {
  await requireNavAccess("/ke-toan");
  const coSo = await layCoSo();
  return <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
    <header className="space-y-1">
      <h1 className="text-title font-semibold text-ink">Kế toán</h1>
      <p className="text-body text-ink-muted">Thống kê theo hàng hoá trong kỳ — số lấy từ chính các phiếu thu ở màn Xuất hoá đơn (đã trừ phiếu huỷ và phần hoàn) — và đặt thuế suất GTGT theo nhóm / từng mặt hàng.</p>
    </header>
    <KeToan coSo={coSo} />
  </main>;
}
