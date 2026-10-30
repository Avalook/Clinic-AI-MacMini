// IN "TÓM TẮT BỆNH ÁN — N LẦN KHÁM GẦN NHẤT" của một khách (Tuyền duyệt bản demo
// 30/10/2026 — thay phiếu đang nhập tay trên Notion). Đặt NGOÀI nhóm (dashboard)
// → không thanh bên, in sạch khổ A4. Cùng cửa với in phiếu khám (`requireInPhieu`:
// khối khám / kết quả + quầy in cho khách). Dữ liệu một nguồn máy chủ
// (`/api/ho-so-kham?xem=tom-tat-kham` → `services/tom_tat_kham.py`).

import { requireInPhieu } from "../../../../lib/clinic-session";
import InTomTatKham from "./InTomTatKham";

export const dynamic = "force-dynamic";

export default async function InTomTatKhamPage({
  params,
}: {
  params: Promise<{ patientId: string }>;
}) {
  await requireInPhieu();
  const { patientId } = await params;
  return <InTomTatKham clinicPatientId={patientId} />;
}
