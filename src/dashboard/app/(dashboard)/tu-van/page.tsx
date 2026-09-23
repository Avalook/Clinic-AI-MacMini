/**
 * Bàn khám TƯ VẤN (dây H1/H3, Tuyền chốt 24/09/2026).
 *
 * Khách khám 5 loại lõi check-in → đo sinh hiệu → HÀNG TƯ VẤN CHUNG (bác sĩ tư
 * vấn nào rảnh thì nhận) → tư vấn ghi vào CHÍNH bệnh án của lượt → bấm "Xong tư
 * vấn" → khối Hành trình chuyển khách sang hàng bác sĩ chính.
 *
 * CÙNG MỘT MÀN với Bàn khám (`BanKham` chế độ "tu_van") — không chép màn thứ hai.
 * Vào được bằng vai (bác sĩ) hoặc bằng QUYỀN "Khám tư vấn" quản lý cấp.
 */

import { getClinicStaffId, requireNavAccess, vaiLamViec } from "@/lib/clinic-session";

import LiveBoardSync from "../LiveBoardSync";
import BanKham from "../ban-kham/BanKham";

export const metadata = { title: "Bàn khám tư vấn · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function TuVanPage() {
  await requireNavAccess("/tu-van");
  const vai = await vaiLamViec((r) => r === "DOCTOR" || r === "TKYK");
  return (
    <>
      <LiveBoardSync />
      <main className="page-in flex flex-col gap-4 p-4 xl:p-6">
        <BanKham
          phongMa={null}
          vai={vai}
          staffId={await getClinicStaffId()}
          cheDo="tu_van"
        />
      </main>
    </>
  );
}
