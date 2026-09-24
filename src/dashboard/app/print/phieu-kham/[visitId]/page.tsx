// IN PHIẾU KHÁM của một lượt (Tuyền 24/09/2026: "chỗ cho in phiếu khám của bệnh
// nhân đâu?"). Đặt NGOÀI nhóm (dashboard) → không thanh bên, in sạch khổ A4.
// Đọc ĐÚNG các nguồn Bàn khám đang đọc (`/api/phieu-kham`), không đọc thẳng
// database, không dựng lại dữ liệu.

import { requireClinicalRole } from "../../../../lib/clinic-session";
import InPhieuKham from "./InPhieuKham";

export const dynamic = "force-dynamic";

export default async function InPhieuKhamPage({
  params,
}: {
  params: Promise<{ visitId: string }>;
}) {
  await requireClinicalRole(); // phiếu chứa hồ sơ khám: ai có khối khám / kết quả
  const { visitId } = await params;
  return <InPhieuKham visitId={visitId} />;
}
