// Lịch sử thao tác (audit log) — image_3.
// Xem ai đã thay đổi gì, lúc nào. Vai vận hành: CSKH / Quản lý / Trưởng ca.
//
// HAI DÒNG SỰ KIỆN, KHÔNG PHẢI MỘT.
//
// Màn này chỉ đọc `event_log`, nhưng workflow kernel — thứ đang chạy ba bảng
// "Mới" (Hàng đợi tiếp nhận, Bàn khám, Bàn thu ngân) — ghi vào bảng riêng
// `work_item_event`. Nghĩa là mọi lần bắt đầu / hoàn tất / bỏ qua / huỷ / bàn
// giao một bước khám KHÔNG xuất hiện ở "Lịch sử thao tác". Quản lý mở màn này
// để trả lời "ai đã làm gì", và nhận một câu trả lời thiếu đúng phần việc lâm
// sàng đang được thao tác nhiều nhất trong ngày.
//
// Hai bảng không gộp được ở tầng SQL qua PostgREST (khác cột, khác khoá), nên
// gộp ở đây: đọc song song, ánh xạ về một hình dạng, trộn theo thời gian.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess } from "../../../lib/clinic-session";
import AuditLogBoard from "./AuditLogBoard";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 200;

interface WorkItemEventRow {
  id: string;
  work_item_id: string;
  command: string;
  from_status: string | null;
  to_status: string;
  actor_staff_id: string | null;
  actor_role: string | null;
  reason: string | null;
  occurred_at: string;
}

export default async function AuditLogPage() {
  await requireNavAccess("/audit-log");
  const supabase = await getSupabaseServer();

  const [eventRes, kernelRes] = await Promise.all([
    supabase
      .from("event_log")
      .select(
        "event_id, event_type, aggregate_type, aggregate_id, payload, metadata, source, occurred_at",
      )
      .order("occurred_at", { ascending: false })
      .limit(PAGE_SIZE),
    supabase
      .from("work_item_event")
      .select(
        "id, work_item_id, command, from_status, to_status, actor_staff_id, actor_role, reason, occurred_at",
      )
      .order("occurred_at", { ascending: false })
      .limit(PAGE_SIZE),
  ]);

  // RLS của event_log giới hạn theo vai vận hành + phòng khám
  // (20260803000004); work_item_event mở cho mọi thành viên của phòng khám.
  // Một trong hai lỗi thì vẫn hiện phần còn lại — nửa lịch sử hữu ích hơn một
  // trang lỗi, miễn là nói rõ phần nào thiếu.
  const events = eventRes.data ?? [];
  const kernel = (kernelRes.data as WorkItemEventRow[] | null) ?? [];

  const kernelAsEvents = kernel.map((r) => ({
    event_id: `wie:${r.id}`,
    event_type: `work_item.${r.command}`,
    aggregate_type: "work_item",
    aggregate_id: r.work_item_id,
    payload: {
      command: r.command,
      from_status: r.from_status,
      to_status: r.to_status,
      reason: r.reason,
    } as Record<string, unknown>,
    metadata: {
      clinic_staff_id: r.actor_staff_id,
      clinic_role: r.actor_role,
      origin: "workflow-kernel",
    } as Record<string, unknown>,
    source: "workflow-kernel",
    occurred_at: r.occurred_at,
  }));

  const merged = [...events, ...kernelAsEvents]
    .sort((a, b) => b.occurred_at.localeCompare(a.occurred_at))
    // Mỗi nguồn lấy PAGE_SIZE dòng mới nhất rồi trộn, nên cắt lại để trang
    // không phình gấp đôi. Ranh giới thời gian vì thế là min(mốc cũ nhất của
    // hai nguồn) — chấp nhận được cho một màn "gần đây", và tổng ở dưới nói rõ.
    .slice(0, PAGE_SIZE);

  const failed = [
    eventRes.error ? "nhật ký hệ thống" : null,
    kernelRes.error ? "nhật ký quy trình" : null,
  ].filter(Boolean);

  return (
    <>
      {failed.length > 0 && (
        <div className="mb-3 rounded-card border border-warning/40 bg-warning-bg px-4 py-2.5 text-sm text-warning">
          Không đọc được {failed.join(" và ")} — danh sách dưới đây đang thiếu
          phần đó.
        </div>
      )}
      <AuditLogBoard events={merged} />
    </>
  );
}
