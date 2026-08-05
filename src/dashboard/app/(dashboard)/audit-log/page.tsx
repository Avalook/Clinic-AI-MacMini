// Lịch sử thao tác (audit log) — ai đã làm gì, với ai, lúc nào.
// Vai vận hành: CSKH / Quản lý / Trưởng ca.
//
// TRANG NÀY TỪNG TỰ LÀM BA VIỆC MÀ NÓ KHÔNG LÀM ĐƯỢC.
//
// Nó gọi thẳng Supabase bằng hai truy vấn phẳng, rồi trộn `event_log` với
// `work_item_event` bằng JavaScript. Ba hệ quả:
//
//   1. KHÔNG BIẾT TÊN AI. Danh tính người thao tác nằm ở
//      `metadata->>'clinic_staff_id'`, và PostgREST không nối được sang `staff`
//      qua một khoá nằm trong jsonb. Nên màn hình đọc `payload.staff_name` —
//      một khoá không đường ghi nào đặt vào — rồi rơi xuống `?? source` và in
//      ra tên đường ghi: "api:booking". Vì `source` là NOT NULL nên 100% dòng
//      hiện tên route thay vì tên người.
//   2. TRỘN RỒI CẮT LÀM MẤT DÒNG. Mỗi nguồn lấy 200 dòng mới nhất, trộn rồi
//      cắt còn 200 — mốc cũ nhất là min của hai nguồn, và những dòng nằm giữa
//      hai mốc biến mất khỏi màn hình mà không ai biết.
//   3. Bảng nhãn sự kiện nằm trong TSX, và có một bảng THỨ HAI ở
//      truong-ca/HistoryClient.tsx. Hai bảng cho cùng một khái niệm thì hai
//      màn nói hai kiểu, và không có gì báo khi chúng lệch — chúng đã lệch.
//
// Cả ba giờ do FastAPI lo: một câu SQL gộp hai nguồn bằng UNION ALL TRƯỚC khi
// sắp xếp, JOIN sang staff/patient để giải tên, và một bảng nhãn duy nhất.

import { requireNavAccess } from "../../../lib/clinic-session";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import AuditLogBoard from "./AuditLogBoard";
import type { AuditEvent } from "./types";

export const dynamic = "force-dynamic";

export default async function AuditLogPage() {
  await requireNavAccess("/audit-log");

  const data = await fetchFromBackend<{
    items: AuditEvent[];
    so_nguoi: number;
  }>("/api/v1/audit/events?limit=200");

  return (
    <>
      {data === null && (
        <div className="mb-3 rounded-card border border-warning/40 bg-warning-bg px-4 py-2.5 text-sm text-warning">
          Không đọc được nhật ký từ máy chủ — thử tải lại trang. Danh sách dưới
          đây trống vì lỗi kết nối, không phải vì không có thao tác nào.
        </div>
      )}
      <AuditLogBoard events={data?.items ?? []} soNguoi={data?.so_nguoi ?? 0} />
    </>
  );
}
