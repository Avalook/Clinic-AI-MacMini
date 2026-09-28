// IN HOÁ ĐƠN THUỐC của một lượt (CSKH 28/09/2026: "3 nút in ra toàn bộ thông
// tin cho khách … hoá đơn thuốc"). Mọi lần thu tiền thuốc ĐÃ THU của lượt, mỗi
// lần một phiếu khổ hoá đơn 80mm — cùng mẫu `PhieuThuGiay` của quầy. Quyền đọc
// do máy chủ gác (GET /api/v1/cashier/phieu-luot/{visit} — quầy thu + CSKH).
import InHoaDonThuoc from "./InHoaDonThuoc";

export const dynamic = "force-dynamic";
export const metadata = { title: "In hoá đơn thuốc · ClinicAI" };

export default async function InHoaDonThuocPage({
  params,
}: {
  params: Promise<{ visitId: string }>;
}) {
  const { visitId } = await params;
  return <InHoaDonThuoc visitId={visitId} />;
}
