/**
 * Bàn khám TƯ VẤN (dây H1/H3, Tuyền chốt 24/09/2026).
 *
 * Khách khám 5 loại lõi check-in → đo sinh hiệu → HÀNG TƯ VẤN CHUNG (bác sĩ tư
 * vấn nào rảnh thì nhận) → tư vấn ghi vào CHÍNH bệnh án của lượt → bấm "Xong tư
 * vấn" → khối Hành trình chuyển khách sang hàng bác sĩ chính.
 *
 * CÙNG MỘT MÀN với Bàn khám (`BanKham` chế độ "tu_van") — không chép màn thứ hai.
 * Vào được bằng lego "Khám tư vấn" (quyền `clinical.intake.perform`) — cửa và
 * nút đều theo lego, không theo vai (đợt 3, 27/09/2026).
 */

import { getClinicStaffId, getNutBanKham, requireNavAccess } from "@/lib/clinic-session";

import LiveBoardSync from "../LiveBoardSync";
import BanKham from "../ban-kham/BanKham";

export const metadata = { title: "Bàn khám tư vấn · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function TuVanPage() {
  await requireNavAccess("/tu-van");
  // Nút bấm theo LEGO của tài khoản, không theo vai (đợt 3, 27/09/2026).
  const nut = await getNutBanKham();
  return (
    <>
      <LiveBoardSync />
      <main className="page-in flex flex-col gap-4 p-4 xl:p-6">
        <BanKham
          phongMa={null}
          nut={nut}
          staffId={await getClinicStaffId()}
          cheDo="tu_van"
        />
      </main>
    </>
  );
}
