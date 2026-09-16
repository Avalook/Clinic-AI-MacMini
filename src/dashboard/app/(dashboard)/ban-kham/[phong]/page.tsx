/** Bàn khám của MỘT phòng: /ban-kham/KN-NOITIET. Xem ../page.tsx. */

import { getClinicRole, requireNavAccess } from "@/lib/clinic-session";

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
  const vai = await getClinicRole();
  return (
    <>
      <LiveBoardSync />
      <main className="page-in flex flex-col gap-4 p-4 xl:p-6">
        <BanKham phongMa={decodeURIComponent(phong)} vai={vai} />
      </main>
    </>
  );
}
