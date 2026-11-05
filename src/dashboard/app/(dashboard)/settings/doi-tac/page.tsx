/**
 * CÀI ĐẶT → ĐỐI TÁC XÉT NGHIỆM (05/11/2026, ADR-0015) — Quản lý thêm / sửa / ngưng đối
 * tác, gán dịch vụ (giá gợi ý, hẹn trả), ngưỡng "đã thu, chưa lấy mẫu". Lego 18 Cài đặt
 * phòng khám (`config.clinic.manage`); máy chủ hỏi lại ở mọi lệnh.
 */

import { requireNavAccess } from "@/lib/clinic-session";

import DoiTacView from "./DoiTacView";

export const metadata = { title: "Đối tác xét nghiệm · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function DoiTacCaiDatPage() {
  await requireNavAccess("/settings/doi-tac");
  return (
    <main className="page-in flex min-w-0 flex-col gap-4 p-4 xl:p-6">
      <DoiTacView />
    </main>
  );
}
