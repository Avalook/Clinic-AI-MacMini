/**
 * Xác nhận tệp kết quả external — kiểm tra vận hành trước khi Bác sĩ duyệt gửi.
 * Dành cho bất kỳ nhân sự nào có capability 'ket_qua.xac_nhan'.
 *
 * CURRENT LIMITATION: SINGLE-PARTNER PILOT ONLY.
 */

import { requireNavAccess } from "@/lib/clinic-session";
import HangChoXacNhanKetQua from "./HangChoXacNhanKetQua";

export const metadata = { title: "Xác nhận kết quả · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function XacNhanKetQuaPage() {
  await requireNavAccess("/xac-nhan-ket-qua");
  return (
    <main className="page-in p-4 xl:p-6">
      <HangChoXacNhanKetQua />
    </main>
  );
}
