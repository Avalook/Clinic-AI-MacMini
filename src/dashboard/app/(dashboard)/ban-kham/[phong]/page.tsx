/** Bàn khám của MỘT phòng: /ban-kham/<room_id> (mã phòng cũ vẫn mở được).
 *  Xem ../page.tsx. */

import { getClinicStaffId, requireNavAccess, vaiBanKham } from "@/lib/clinic-session";

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
  // Nút bấm theo QUYỀN (28/09/2026) — người cùng phòng thao tác như nhau.
  const vai = await vaiBanKham();
  return (
    <>
      <LiveBoardSync />
      <main className="page-in flex flex-col gap-4 p-4 xl:p-6">
        <BanKham phongMa={decodeURIComponent(phong)} vai={vai} staffId={await getClinicStaffId()} />
      </main>
    </>
  );
}
