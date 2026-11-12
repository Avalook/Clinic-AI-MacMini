/**
 * KHO EMAIL KẾT QUẢ (TẠM) — Gmail G2b (09/11/2026). Mọi thư kết quả đối tác gửi về
 * Gmail phòng khám (cả thư cũ, chưa ghép). Lego `kho_email` — cấp RIÊNG từng người
 * (không nhóm mẫu nào); máy chủ trả 404 cho người không có quyền. Chỉ xem.
 */

import { requireNavAccess } from "@/lib/clinic-session";

import KhoEmail from "./KhoEmail";

export const metadata = { title: "Kho email kết quả · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function KhoEmailPage() {
  await requireNavAccess("/ban-xet-nghiem/kho-email");
  return (
    <main className="page-in flex min-w-0 flex-col gap-4 p-4 xl:p-6">
      <KhoEmail />
    </main>
  );
}
