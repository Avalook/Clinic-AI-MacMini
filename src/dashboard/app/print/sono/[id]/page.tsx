// PHIẾU IN SIÊU ÂM / XÉT NGHIỆM KIỂU CŨ (bảng `service_log`) — OFF 24/09/2026.
//
// SITEMAP: "CẦN QUYẾT — không chỗ nào dẫn tới". Claude chốt tắt: phiếu in kết
// quả hiện hành là `/print/ket-qua/[orderId]` (engine phiếu). Trang cũ từng đọc
// thẳng `service_log` bằng Supabase; nay không đọc gì. Bản cũ còn trong lịch sử
// git (commit trước 24/09) — bật lại thì khôi phục file ấy.

import { requireClinicRole } from "../../../../lib/clinic-session";

export const dynamic = "force-dynamic";

export default async function SonoPrintPage() {
  await requireClinicRole();
  return (
    <main className="p-6 text-sm text-ink-muted">
      Phiếu in kiểu cũ đã tắt. Mở kết quả từ phiếu khám (mục C) để in bằng phiếu
      kết quả hiện hành.
    </main>
  );
}
