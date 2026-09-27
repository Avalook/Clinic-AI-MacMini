// IN PHIẾU KHÁM của một lượt (Tuyền 24/09/2026: "chỗ cho in phiếu khám của bệnh
// nhân đâu?"). Đặt NGOÀI nhóm (dashboard) → không thanh bên, in sạch khổ A4.
// Đọc ĐÚNG các nguồn Bàn khám đang đọc (`/api/phieu-kham`), không đọc thẳng
// database, không dựng lại dữ liệu.

import { requireInPhieu } from "../../../../lib/clinic-session";
import InPhieuKham from "./InPhieuKham";

export const dynamic = "force-dynamic";

export default async function InPhieuKhamPage({
  params,
}: {
  params: Promise<{ visitId: string }>;
}) {
  // Phiếu chứa hồ sơ khám: ai có khối khám / kết quả, VÀ quầy tiếp đón / thu tiền /
  // nhà thuốc in cho khách (27/09/2026 — `QUYEN_IN_PHIEU`, chỉ đọc).
  await requireInPhieu();
  const { visitId } = await params;
  return <InPhieuKham visitId={visitId} />;
}
