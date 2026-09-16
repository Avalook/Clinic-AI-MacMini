/**
 * Duyệt kết quả — bác sĩ đánh giá và phê duyệt cho gửi, theo TỪNG chỉ định.
 * Thay cho /result-review (duyệt theo tệp rời và theo bảng xét nghiệm cũ).
 */

import { requireNavAccess } from "@/lib/clinic-session";

import DuyetKetQua from "./DuyetKetQua";

export const metadata = { title: "Duyệt kết quả · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function DuyetKetQuaPage() {
  await requireNavAccess("/duyet-ket-qua");
  return (
    <main className="page-in p-4 xl:p-6">
      <DuyetKetQua />
    </main>
  );
}
