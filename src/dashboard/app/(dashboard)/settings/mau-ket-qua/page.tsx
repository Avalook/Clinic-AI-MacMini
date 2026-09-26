/**
 * MẪU KẾT QUẢ (27/09/2026 — Tuyền: "làm tiếp màn sửa/gắn mẫu kết quả"). Bản giao
 * diện mẫu: xung đột giữa các nguồn thì chọn theo file chuẩn, NHƯNG hệ thống phải
 * mở cho người dùng sửa sau — giá, mẫu, gắn mẫu. Màn này là phần "mẫu":
 *   · Gắn mẫu cho dịch vụ (quyền `catalogue.result_template.manage`)
 *   · Sửa / tạo mẫu, xuất bản bản mới (quyền `catalogue.form_template.publish`)
 * Lego 18 Cài đặt phòng khám (khối "Danh mục & biểu mẫu").
 */

import { requireNavAccess } from "@/lib/clinic-session";

import MauKetQuaView from "./MauKetQuaView";

export const metadata = { title: "Mẫu kết quả · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function MauKetQuaPage() {
  await requireNavAccess("/settings/mau-ket-qua");
  return (
    <main className="page-in flex flex-col gap-4 p-4 xl:p-6">
      <MauKetQuaView />
    </main>
  );
}
