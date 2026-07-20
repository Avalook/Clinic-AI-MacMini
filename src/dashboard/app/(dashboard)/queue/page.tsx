// Trang lẻ "SỐ THỨ TỰ GỌI KHÁM" (Model ②).
//   • Số vé (queue_number) = ĐỊNH DANH cấp lúc đến, KHÔNG phải thứ tự gọi.
//   • Thứ tự GỌI do BACKEND tính (/api/v1/queue → call_rank): ƯT → có hẹn đến đúng
//     giờ (≤ giờ hẹn + 10') → walk-in / đến trễ theo GIỜ ĐẾN. Gọi bệnh nhân theo TÊN.
// Logic xếp hạng KHÔNG còn ở frontend (Phase 4 cluster #5). Chỉ đọc, tự refresh 30s.

import { requireNavAccess } from "../../../lib/clinic-session";
import QueueBoard, { type QueueRow } from "./QueueBoard";

export const dynamic = "force-dynamic";

export default async function QueuePage() {
  await requireNavAccess("/queue");

  const base = process.env.CLINIC_API_URL;
  // VN calendar day (YYYY-MM-DD); the backend filters by Asia/Ho_Chi_Minh bounds.
  const day = new Date().toLocaleDateString("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
  });

  let rows: QueueRow[] = [];
  let error: string | null = null;
  try {
    if (!base) throw new Error("CLINIC_API_URL chưa cấu hình");
    const res = await fetch(`${base}/api/v1/queue?date=${day}`, {
      headers: { "X-API-Key": process.env.BACKEND_API_KEY ?? "" },
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
