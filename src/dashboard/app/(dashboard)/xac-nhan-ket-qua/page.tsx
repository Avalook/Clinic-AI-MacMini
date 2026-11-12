/**
 * Xác nhận tệp kết quả đối tác (đúng khách, đúng chỉ định) trước khi CSKH gửi khách.
 * Ai có quyền Xác nhận kết quả (`result.file.confirm`) đều vào được.
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
