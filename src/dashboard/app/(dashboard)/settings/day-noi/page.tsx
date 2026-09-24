/**
 * DÂY NỐI NGHIỆP VỤ (nhóm 5, Tuyền chốt 24/09/2026): "đường nối H1–H8 phải
 * CUSTOM được". Quản lý chỉnh: loại khám qua tư vấn / đi thẳng phòng, bật tắt
 * tự xếp phòng, thời hạn nhắc, người nhận chuông, vị trí trực. Dây LÕI (dòng
 * thời gian, trách nhiệm tiền) không có ở đây.
 */

import { requireNavAccess } from "@/lib/clinic-session";

import DayNoiBoard from "./DayNoiBoard";

export const metadata = { title: "Dây nối nghiệp vụ · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function DayNoiPage() {
  await requireNavAccess("/settings/day-noi");
  return (
    <main className="page-in flex flex-col gap-4 p-4 xl:p-6">
      <DayNoiBoard />
    </main>
  );
}
