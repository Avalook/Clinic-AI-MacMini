// IN MỌI PHIẾU KẾT QUẢ của một lượt (CSKH 28/09/2026: "phiếu siêu âm / thủ thuật
// / … các ảnh nhá"). Mỗi chỉ định có kết quả = ĐÚNG phiếu phòng in
// (`/print/ket-qua/[order]`, component `InKetQua` nhúng), kết quả + trang ảnh,
// sang trang mới giữa hai chỉ định. Cửa trang như in phiếu kết quả một chỉ định;
// máy chủ gác từng phiếu (`/api/v1/phieu/in/{order}` — quyền in phiếu).
import { requireInPhieu } from "../../../../lib/clinic-session";
import InKetQuaLuot from "./InKetQuaLuot";

export const dynamic = "force-dynamic";
export const metadata = { title: "In kết quả · ClinicAI" };

export default async function InKetQuaLuotPage({
  params,
}: {
  params: Promise<{ visitId: string }>;
}) {
  await requireInPhieu();
  const { visitId } = await params;
  return <InKetQuaLuot visitId={visitId} />;
}
