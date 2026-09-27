// VIỆC CẦN XỬ LÝ — chỗ những trách nhiệm không được rơi hiện ra.
//
// Mở một việc mà không màn nào hiện nó thì vẫn là rơi, chỉ là rơi vào database.
// Màn này đọc bảng việc của khu vận hành: khách đã trả tiền mà dịch vụ không
// làm được, và dịch vụ bị dừng giữa chừng cần người quyết làm lại.
//
// Màn KHÔNG có luật riêng: danh sách là `GET /api/work-items`, đóng việc là
// lệnh `complete` của kernel — đúng hai đường mà các bảng việc khác đang dùng.

import { requireNavAccess } from "@/lib/clinic-session";
import BangViecCanXuLy from "./BangViecCanXuLy";

export const dynamic = "force-dynamic";
export const metadata = { title: "Việc cần xử lý · ClinicAI" };

export default async function TrangViecCanXuLy() {
  await requireNavAccess("/viec-can-xu-ly");
  return (
    // KHÔNG <main> / <h1> thứ hai (đợt 3, 27/09/2026): khung trang (Shell) đã có
    // <main> và <h1>; màn con chỉ là một vùng có tiêu đề cấp 2.
    <section aria-labelledby="viec-can-xu-ly-tieu-de" className="page-in flex flex-col gap-4">
      <header>
        <h2 id="viec-can-xu-ly-tieu-de" className="text-title font-semibold text-ink">
          Việc cần xử lý
        </h2>
        <p className="text-body text-ink-muted">
          Khách đã trả tiền mà dịch vụ không làm được, dịch vụ bị dừng giữa chừng,
          và dịch vụ cần xếp lại phòng. Xử lý xong thì bấm “Đã xử lý”.
        </p>
      </header>
      <BangViecCanXuLy />
    </section>
  );
}
