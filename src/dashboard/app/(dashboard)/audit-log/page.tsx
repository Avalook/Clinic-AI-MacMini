// Lịch sử thao tác (audit log) — image_3.
// Xem ai đã thay đổi gì, lúc nào. Chỉ MANAGEMENT + TRUONG_CA.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess } from "../../../lib/clinic-session";
import AuditLogBoard from "./AuditLogBoard";

export const dynamic = "force-dynamic";

export default async function AuditLogPage() {
  await requireNavAccess("/audit-log");
  const supabase = await getSupabaseServer();

  // actor_staff_id (migration 20260802000003) là cột thật có khoá ngoại, nên
  // tên người thao tác lấy được bằng một lần join của PostgREST — không phải
  // đọc bảng staff rồi ghép tay ở client. RLS trên staff vẫn áp: chỉ nhân sự
  // cùng phòng khám mới hiện tên.
  const { data: events, error } = await supabase
    .from("event_log")
    .select("*, actor:staff!event_log_actor_staff_id_fkey(full_name)")
    .order("occurred_at", { ascending: false })
    .limit(200);

  if (error) {
    return (
      <div className="p-6 text-sm text-danger">
        Không đọc được lịch sử: {error.message}
      </div>
    );
  }

  return <AuditLogBoard events={events ?? []} />;
}