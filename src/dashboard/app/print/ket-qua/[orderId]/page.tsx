// IN PHIẾU KẾT QUẢ của một chỉ định (23/09/2026 khuya — Tuyền: "sửa lại rồi lưu
// rồi in được"). Đặt NGOÀI nhóm (dashboard) → không thanh bên, in sạch khổ A4.
// Dữ liệu đọc qua FastAPI (`/api/phieu?in=`), không đọc thẳng database.

import { requireClinicRole } from "../../../../lib/clinic-session";
import InKetQua from "./InKetQua";

export const dynamic = "force-dynamic";

export default async function InKetQuaPage({
  params,
}: {
  params: Promise<{ orderId: string }>;
}) {
  await requireClinicRole();
  const { orderId } = await params;
  return <InKetQua orderId={orderId} />;
}
