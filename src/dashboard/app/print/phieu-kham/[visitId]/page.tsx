// IN PHIẾU KHÁM của một lượt (Tuyền 24/09/2026: "chỗ cho in phiếu khám của bệnh
// nhân đâu?"). Đặt NGOÀI nhóm (dashboard) → không thanh bên, in sạch khổ A4.
// Đọc ĐÚNG các nguồn Bàn khám đang đọc (`/api/phieu-kham`), không đọc thẳng
// database, không dựng lại dữ liệu.

import { requireInPhieu } from "../../../../lib/clinic-session";
import InPhieuKham from "./InPhieuKham";

export const dynamic = "force-dynamic";

const PHAN = ["tom_tat", "don", "cls_kem", "cls", "cls_anh"] as const;

export default async function InPhieuKhamPage({
  params,
  searchParams,
}: {
  params: Promise<{ visitId: string }>;
  searchParams: Promise<{ phan?: string }>;
}) {
  // Phiếu chứa hồ sơ khám: ai có khối khám / kết quả, VÀ quầy tiếp đón / thu tiền /
  // nhà thuốc in cho khách (27/09/2026 — `QUYEN_IN_PHIEU`, chỉ đọc).
  await requireInPhieu();
  const { visitId } = await params;
  // `?phan=` (CSKH 28/09/2026): mở ra là CHỈ phần ấy — hồ sơ khám / kết quả /
  // đơn thuốc — để tải PDF trả khách. Giá trị lạ → cả phiếu.
  const { phan } = await searchParams;
  const chiPhan = PHAN.find((p) => p === phan);
  return <InPhieuKham visitId={visitId} chiPhan={chiPhan} />;
}
