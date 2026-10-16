// IN TEM LÔ THUỐC (G3b, 14/10/2026): mỗi lô một tem mã vạch (mã tem riêng của
// lô + tên thuốc + số lô + hạn) để dán lên hộp lúc nhập; quét tem ra đúng lô.
// `?ids=<lô,lô…>` hoặc `?phieu=<phiếu nhập>`. Quyền đọc do máy chủ gác
// (`GET /api/v1/pharmacy/tem-lo` — người có quyền xem nhà thuốc).
import InTemLo from "./InTemLo";

export const dynamic = "force-dynamic";
export const metadata = { title: "In tem lô thuốc · ClinicAI" };

export default async function InTemLoPage({
  searchParams,
}: {
  searchParams: Promise<{ ids?: string; phieu?: string }>;
}) {
  const { ids, phieu } = await searchParams;
  return <InTemLo ids={ids ?? ""} phieu={phieu ?? ""} />;
}
