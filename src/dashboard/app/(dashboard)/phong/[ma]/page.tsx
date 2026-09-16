/**
 * Phòng dịch vụ — siêu âm, thủ thuật, lấy mẫu (Tuyền chốt 16/09/2026).
 *
 * Đường dẫn theo MÃ PHÒNG (`/phong/KN-SA1`), không theo mã UUID: thanh bên khai
 * sẵn được, gửi link cho nhau đọc được. Mã phòng khớp `clinic_room.code`.
 *
 * Thay cho: Điều dưỡng siêu âm (/sono), Khám siêu âm (/sieu-am), Làm thủ thuật
 * & dịch vụ (/service-queue), Lấy mẫu xét nghiệm (/lab-queue) — bốn màn đọc bốn
 * nguồn khác nhau cho cùng một việc "khách vào phòng làm chỉ định".
 */

import { requireNavAccess } from "@/lib/clinic-session";

import LiveBoardSync from "../../LiveBoardSync";
import PhongDichVu from "./PhongDichVu";

export const dynamic = "force-dynamic";

export async function generateMetadata() {
  return { title: "Phòng · ClinicAI" };
}

export default async function PhongPage({
  params,
}: {
  params: Promise<{ ma: string }>;
}) {
  const { ma } = await params;
  await requireNavAccess(`/phong/${ma}`);
  return (
    <>
      <LiveBoardSync />
      <main className="page-in p-4 xl:p-6">
        <PhongDichVu ma={decodeURIComponent(ma)} />
      </main>
    </>
  );
}
