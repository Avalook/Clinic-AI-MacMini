// Command Center — Cổng trung tâm điều khiển toàn hệ thống.
// Chỉ MANAGEMENT + TRUONG_CA (isOpsAdmin) mới được vào.
// Tổng hợp: trạng thái hệ thống, vai trò, màn hình, hạ tầng, số liệu vận hành.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { VN_TZ } from "../../../lib/datetime";
import { requireNavAccess, getClinicRole } from "../../../lib/clinic-session";
import { isOpsAdmin } from "../../../lib/roles";
import PortalBoard from "./PortalBoard";

export const dynamic = "force-dynamic";

export default async function PortalPage() {
  await requireNavAccess("/portal");
  const role = await getClinicRole();
  if (!role || !isOpsAdmin(role)) {
    // requireNavAccess đã redirect, nhưng giữ guard phòng hờ.
    return null;
  }

  const supabase = await getSupabaseServer();

  // Danh sách nhân viên KHÔNG phụ thuộc mấy con số bên dưới — nó chỉ nằm
  // trước vì được viết trước. Đợi nó xong rồi mới bắn khối kia là cộng thêm
  // một lượt ~210ms sang Seoul cho không.
  const qStaff = supabase
    .from("staff")
    .select(
      "id, full_name, short_name, primary_department, employment_type, is_active, auth_user_id",
    )
    .order("primary_department", { ascending: true })
    .order("full_name", { ascending: true });

  // Lấy số liệu hôm nay: lịch hẹn, bệnh nhân, lượt khám
  const vnNow = new Date();
  const vnToday = new Date(
    vnNow.toLocaleString("en-US", { timeZone: VN_TZ }),
  );
  const dayStart = new Date(
    Date.UTC(
      vnToday.getFullYear(),
      vnToday.getMonth(),
      vnToday.getDate(),
      0,
      0,
      0,
    ),
  ).toISOString();
  const dayEnd = new Date(
    Date.UTC(
      vnToday.getFullYear(),
      vnToday.getMonth(),
      vnToday.getDate(),
      23,
      59,
      59,
      999,
    ),
  ).toISOString();

  const [
    { data: staffRows },
    apptTodayRes,
    patientTodayRes,
    visitTodayRes,
    pendingTaskRes,
    eventLogRes,
  ] = await Promise.all([
    qStaff,
    supabase
      .from("appointment")
      .select("*", { count: "exact", head: true })
      .gte("slot_start", dayStart)
      .lt("slot_start", dayEnd),
    supabase
      .from("patient")
      .select("*", { count: "exact", head: true })
      .gte("created_at", dayStart)
      .lt("created_at", dayEnd),
    supabase
      .from("visit")
      .select("*", { count: "exact", head: true })
      .gte("created_at", dayStart)
      .lt("created_at", dayEnd),
    supabase
      .from("work_item")
      .select("*", { count: "exact", head: true })
      .in("status", ["PENDING", "IN_PROGRESS"]),
    supabase
      .from("event_log")
      .select("event_id, event_type, aggregate_type, source, occurred_at")
      .order("occurred_at", { ascending: false })
      .limit(10),
  ]);

  const staff = (staffRows as
    | {
        id: string;
        full_name: string;
        short_name: string | null;
        primary_department: string;
        employment_type: string;
        is_active: boolean;
        auth_user_id: string | null;
      }[]
    | null) ?? [];

  const events = (eventLogRes.data as
    | {
        event_id: string;
        event_type: string;
        aggregate_type: string;
        source: string;
        occurred_at: string;
      }[]
    | null) ?? [];

  return (
    <PortalBoard
      staff={staff}
      counts={{
        appointmentsToday: apptTodayRes.count ?? 0,
        patientsToday: patientTodayRes.count ?? 0,
        visitsToday: visitTodayRes.count ?? 0,
        pendingTasks: pendingTaskRes.count ?? 0,
      }}
      recentEvents={events}
    />
  );
}