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

// Nhập hàm requireNavAccess để kiểm tra quyền truy cập trang (dựa trên vai trò người dùng)
import { requireNavAccess } from "../../../lib/clinic-session";
// Nhập hàm fetchFromBackend để gọi API backend FastAPI phía server
import { fetchFromBackend } from "../../../lib/backend-proxy";
// Nhập component AuditLogBoard để hiển thị bảng lịch sử thao tác
import AuditLogBoard from "./AuditLogBoard";
// Nhập kiểu dữ liệu AuditEvent từ file types
import type { AuditEvent } from "./types";

// Ép Next.js render trang này động (không cache) — luôn lấy dữ liệu mới nhất
export const dynamic = "force-dynamic";

// Component chính của trang lịch sử thao tác (server component)
export default async function AuditLogPage() {
  // Kiểm tra quyền truy cập trang /audit-log — nếu không có quyền sẽ redirect hoặc từ chối
  await requireNavAccess("/audit-log");

  // Gọi API backend FastAPI để lấy danh sách sự kiện audit (tối đa 200 dòng)
  const data = await fetchFromBackend<{
    items: AuditEvent[]; // Danh sách các sự kiện audit
    so_nguoi: number; // Số người thao tác
  }>("/api/v1/audit/events?limit=200");

  return (
    <>
      {/* Nếu không lấy được dữ liệu từ backend (data === null) */}
      {data === null && (
        // Hiển thị cảnh báo màu vàng ở đầu trang
        <div className="mb-3 rounded-card border border-warning/40 bg-warning-bg px-4 py-2.5 text-sm text-warning">
          Không đọc được nhật ký từ máy chủ — thử tải lại trang. Danh sách dưới
          đây trống vì lỗi kết nối, không phải vì không có thao tác nào.
        </div>
      )}
      {/* Render component AuditLogBoard với danh sách sự kiện (rỗng nếu không có dữ liệu) và số người thao tác */}
      <AuditLogBoard events={data?.items ?? []} soNguoi={data?.so_nguoi ?? 0} />
    </>
  );
}