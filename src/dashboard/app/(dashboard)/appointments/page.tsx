// Appointment tracking workspace. The page only reads the caller-visible rows;
// capacity and temporary holds are deliberately not represented until FastAPI
// exposes their contract.

import {
  getActiveStaff,
  getClinicRole,
  requireNavAccess,
} from "../../../lib/clinic-session";
import { vnTodayRangeUtc } from "../../../lib/datetime";
import { isDoctorRole } from "../../../lib/roles";
import { getSupabaseServer } from "../../../lib/supabase-server";
import AppointmentsRealtime from "./AppointmentsRealtime";
import AppointmentsWorkspace, {
  type AppointmentRange,
} from "./AppointmentsWorkspace";
import { KANBAN_SELECT, type KanbanRow } from "./AppointmentsKanban";

export const dynamic = "force-dynamic";

const BOARD_STATUSES = [
  "SCHEDULED",
  "CSKH_CONFIRMED",
  "CONFIRMED",
  "CHECKED_IN",
  "COMPLETED",
];

const DAY_MS = 24 * 60 * 60 * 1000;
const RANGE_DAYS: Record<AppointmentRange, number> = {
  day: 1,
  week: 7,
  month: 30,
};

export default async function AppointmentsPage({
  searchParams,
}: {
  searchParams: Promise<{ range?: string }>;
}) {
  await requireNavAccess("/appointments");
  const { range: rawRange } = await searchParams;
  const range: AppointmentRange =
    rawRange === "day" || rawRange === "month" ? rawRange : "week";

  const role = await getClinicRole();
  const staff = await getActiveStaff();
  const isDoctor = isDoctorRole(role);
  const doctorId = isDoctor && staff ? staff.id : null;
  const supabase = await getSupabaseServer();
  const { startUtc: dayStart, endUtc: dayEnd } = vnTodayRangeUtc();
  const upcomingEnd = new Date(
    new Date(dayEnd).getTime() + RANGE_DAYS[range] * DAY_MS,
  ).toISOString();

  const buildQuery = (window: "today" | "upcoming") => {
    let query = supabase
      .from("appointment")
      .select(KANBAN_SELECT)
      .in("status", BOARD_STATUSES);
    query =
      window === "today"
        ? query.gte("slot_start", dayStart).lt("slot_start", dayEnd)
        : query.gte("slot_start", dayEnd).lt("slot_start", upcomingEnd);
    query = query.order("slot_start", { ascending: true }).limit(300);
    return doctorId ? query.eq("doctor_id", doctorId) : query;
  };

  const [todayRes, upcomingRes] = await Promise.all([
    buildQuery("today"),
    buildQuery("upcoming"),
  ]);
  const today = (todayRes.data as KanbanRow[] | null) ?? [];
  const upcoming = (upcomingRes.data as KanbanRow[] | null) ?? [];
  const error = todayRes.error ?? upcomingRes.error;

  return (
    <div className="space-y-3">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-brand-700">
            Điều phối lịch hẹn
          </p>
          <h1 className="mt-1 text-xl font-semibold text-ink">
            Lịch hẹn{isDoctor && staff ? ` của ${staff.full_name}` : ""}
          </h1>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
            <p className="text-sm text-ink-muted">
              {isDoctor
                ? "Chỉ hiển thị lịch hẹn của bạn."
                : "Theo dõi lịch hẹn từ dữ liệu hiện có."}
            </p>
            <AppointmentsRealtime />
          </div>
        </div>
      </header>

      {error ? (
        <div className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">
          {error.message}
        </div>
      ) : null}

      <AppointmentsWorkspace
        today={today}
        upcoming={upcoming}
        range={range}
        canAct={isDoctor}
        staffId={staff?.id ?? null}
      />
    </div>
  );
}
