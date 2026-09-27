/**
 * Bàn khám — bác sĩ và thư ký đi kèm (Tuyền chốt 16/09/2026).
 *
 * Một màn cho mọi loại khám: phiếu mở theo dịch vụ khách đặt (Phụ khoa / Sản /
 * Nội tiết / Hiếm muộn / Nam khoa), hàng chờ theo PHÒNG trong lịch hôm nay.
 * Thay cho "Bàn khám (tất cả)" và năm màn Khám nội tiết / phụ khoa / sản /
 * hiếm muộn / nam khoa — năm màn ấy đặt tên theo phiếu, không theo nơi làm việc.
 */

import { getClinicStaffId, requireNavAccess, vaiBanKham } from "@/lib/clinic-session";

import LiveBoardSync from "../LiveBoardSync";
import BanKham from "./BanKham";

export const metadata = { title: "Bàn khám · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function BanKhamPage() {
  await requireNavAccess("/ban-kham");
  // Nút bấm theo QUYỀN (28/09/2026) — người cùng phòng thao tác như nhau.
  const vai = await vaiBanKham();
  return (
    <>
      <LiveBoardSync />
      <main className="page-in flex flex-col gap-4 p-4 xl:p-6">
        <BanKham phongMa={null} vai={vai} staffId={await getClinicStaffId()} />
      </main>
    </>
  );
}
