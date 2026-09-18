/** Bàn khám của MỘT phòng: /ban-kham/KN-NOITIET. Xem ../page.tsx. */

import { getClinicStaffId, requireNavAccess, vaiLamViec } from "@/lib/clinic-session";

import LiveBoardSync from "../../LiveBoardSync";
import BanKham from "../BanKham";

export const metadata = { title: "Bàn khám · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function BanKhamPhongPage({
  params,
}: {
  params: Promise<{ phong: string }>;
}) {
  const { phong } = await params;
  await requireNavAccess(`/ban-kham/${phong}`);
  // Nút bấm theo GIẤY PHÉP bác sĩ / thư ký nếu tài khoản có.
  const vai = await vaiLamViec((r) => r === "DOCTOR" || r === "TKYK");
  return (
    <>
      <LiveBoardSync />
      <main className="page-in flex flex-col gap-4 p-4 xl:p-6">
        <BanKham phongMa={decodeURIComponent(phong)} vai={vai} staffId={await getClinicStaffId()} />
      </main>
    </>
  );
}
