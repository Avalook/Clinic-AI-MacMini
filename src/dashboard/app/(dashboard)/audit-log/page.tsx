// Lịch sử thao tác (audit log) — image_3.
// Xem ai đã thay đổi gì, lúc nào. Chỉ MANAGEMENT + TRUONG_CA.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess } from "../../../lib/clinic-session";
import AuditLogBoard from "./AuditLogBoard";

export const dynamic = "force-dynamic";

export default async function AuditLogPage() {
  await requireNavAccess("/audit-log");
  const supabase = await getSupabaseServer();

  const { data: events, error } = await supabase
    .from("event_log")
    .select("*")
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