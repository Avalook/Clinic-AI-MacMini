// Trang lẻ "SỐ THỨ TỰ GỌI KHÁM" (Model ②).
//   • Số vé (queue_number) = ĐỊNH DANH cấp lúc đến, KHÔNG phải thứ tự gọi.
//   • Thứ tự GỌI do BACKEND tính (/api/v1/queue → call_rank): ƯT → có hẹn đến đúng
//     giờ (≤ giờ hẹn + 10') → walk-in / đến trễ theo GIỜ ĐẾN. Gọi bệnh nhân theo TÊN.
// Logic xếp hạng KHÔNG còn ở frontend (Phase 4 cluster #5). Chỉ đọc, tự refresh 30s.

import { getCallerAuthHeaders } from "../../../lib/backend-proxy";
import { VN_TZ } from "../../../lib/datetime";
import { requireNavAccess } from "../../../lib/clinic-session";
import QueueBoard, { type QueueRow } from "./QueueBoard";

export const dynamic = "force-dynamic";

export default async function QueuePage() {
  await requireNavAccess("/queue");

  const base = process.env.CLINIC_API_URL;
  // VN calendar day (YYYY-MM-DD); the backend filters by Asia/Ho_Chi_Minh bounds.
  const day = new Date().toLocaleDateString("en-CA", {
    timeZone: VN_TZ,
  });

  let rows: QueueRow[] = [];
  let error: string | null = null;
  try {
    if (!base) throw new Error("CLINIC_API_URL chưa cấu hình");
    // The queue is per-clinic and returns patient names, so the backend now
    // requires the caller's own token, not just the shared API key (W8).
    // Header lấy từ chỗ dùng chung. Bản cũ tự dựng ở đây và QUÊN getUser(),
    // nên sau một tiếng token hết hạn là màn này báo "chưa đăng nhập" trong
    // khi mọi trang khác vẫn chạy — xem getCallerAuthHeaders (backend-proxy).
    const headers = await getCallerAuthHeaders();
    if (!headers) throw new Error("Chưa đăng nhập");
    const res = await fetch(`${base}/api/v1/queue?date=${day}`, {
      headers,
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = (await res.json()) as { rows: QueueRow[] };
    rows = data.rows ?? [];
  } catch (e) {
    error = e instanceof Error ? e.message : "Không tải được hàng đợi";
  }

  return <QueueBoard rows={rows} error={error} />;
}
