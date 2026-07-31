// Appointments page — two Kanban boards ("Hôm nay" / "Sắp tới"), each with
// three status columns: Chờ xác nhận → Đã xác nhận → Đã khám xong.
// Read-only data; CCCD is never shown (D-identity gate).
// PER-DOCTOR SCOPE: ?scope=me narrows to the logged-in doctor's appointments.
// UPCOMING RANGE: ?range=day|week|month limits the "Sắp tới" board window.

import Link from "next/link";
import AppointmentsKanban, {
  KANBAN_SELECT,
  type KanbanRow,
} from "./AppointmentsKanban";
import AppointmentsRealtime from "./AppointmentsRealtime";
import { getSupabaseServer } from "../../../lib/supabase-server";
import {
  getClinicRole,
  getActiveStaff,
  requireNavAccess,
} from "../../../lib/clinic-session";
import { isDoctorRole } from "../../../lib/roles";
import { vnTodayRangeUtc } from "../../../lib/datetime";

export const dynamic = "force-dynamic";

// Happy-path workflow statuses (DOCTOR_DECLINED is surfaced separately via the
// reassign notice; CANCELLED / NO_SHOW live in patient history).
const BOARD_STATUSES = [
  "SCHEDULED",
  "CSKH_CONFIRMED",
  "CONFIRMED",
  "CHECKED_IN",
  "COMPLETED",
];

const DAY_MS = 24 * 60 * 60 * 1000;
type Range = "day" | "week" | "month";
const RANGE_DAYS: Record<Range, number> = { day: 1, week: 7, month: 30 };
const RANGE_LABEL: Record<Range, string> = {
  day: "Ngày",
  week: "Tuần",
  month: "Tháng",
};

export default async function AppointmentsPage({
  searchParams,
}: {
  searchParams: Promise<{ range?: string }>;
}) {
  await requireNavAccess("/appointments");
  const { range: rawRange } = await searchParams;

  const role = await getClinicRole();
  const staff = await getActiveStaff();
  // Bác sĩ CHỈ xem lịch của mình (không có lựa chọn "Tất cả"). CSKH/Quản lý
  // điều phối nên xem toàn bộ.
  const isDoctor = isDoctorRole(role);
  const meId = isDoctor && staff ? staff.id : null;

  const range: Range =
    rawRange === "day" || rawRange === "month" ? rawRange : "week";

  const supabase = await getSupabaseServer();
  const { startUtc: dayStart, endUtc: dayEnd } = vnTodayRangeUtc();
  // Upcoming window: from end-of-today out to N days, per the range filter.
  const upcomingEnd = new Date(
    new Date(dayEnd).getTime() + RANGE_DAYS[range] * DAY_MS,
  ).toISOString();

  // Today + upcoming fetched in parallel (cheap now the function runs in the
  // same region as Supabase).
  const buildQuery = (which: "today" | "upcoming") => {
    let q = supabase
      .from("appointment")
      .select(KANBAN_SELECT)
      .in("status", BOARD_STATUSES);
    q =
      which === "today"
        ? q.gte("slot_start", dayStart).lt("slot_start", dayEnd)
        : q.gte("slot_start", dayEnd).lt("slot_start", upcomingEnd);
    q = q.order("slot_start", { ascending: true }).limit(300);
    if (meId) q = q.eq("doctor_id", meId);
    return q;
  };

  const [todayRes, upcomingRes] = await Promise.all([
    buildQuery("today"),
    buildQuery("upcoming"),
  ]);

  const today = (todayRes.data as KanbanRow[] | null) ?? [];
  const upcoming = (upcomingRes.data as KanbanRow[] | null) ?? [];
  const error = todayRes.error ?? upcomingRes.error;

  const rangeHref = (r: Range): string =>
    r === "week" ? "/appointments" : `/appointments?range=${r}`;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-ink">
            Lịch hẹn{isDoctor && staff ? ` của ${staff.full_name}` : ""}
          </h1>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <p className="text-sm text-ink-muted">
              {isDoctor
                ? "Chỉ hiển thị lịch hẹn của bạn."
                : "Bảng theo dõi xác nhận lịch. Read-only."}
            </p>
            <AppointmentsRealtime />
          </div>
        </div>
      </header>

      {error && (
        <div className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
          {error.message}
        </div>
      )}

      <AppointmentsKanban
        title="Hôm nay"
        rows={today}
        canAct={isDoctor}
        staffId={staff?.id ?? null}
      />

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold text-ink">
            Sắp tới
            <span className="ml-2 text-sm font-normal text-ink-muted">
              ({upcoming.length} · {RANGE_DAYS[range]} ngày tới)
            </span>
          </h2>
          {/* Range filter: Ngày / Tuần / Tháng. */}
          <div
            className="flex gap-1 rounded-lg bg-surface-sunken p-1"
            role="group"
            aria-label="Khoảng thời gian"
          >
            {(["day", "week", "month"] as Range[]).map((r) => (
              <Link
                key={r}
                href={rangeHref(r)}
                className={
                  r === range
                    ? "rounded-md bg-white px-3 py-1 text-xs font-medium text-ink shadow-[0_1px_2px_rgba(0,0,0,0.08)]"
                    : "rounded-md px-3 py-1 text-xs text-ink-muted hover:text-ink"
                }
              >
                {RANGE_LABEL[r]}
              </Link>
            ))}
          </div>
        </div>

        <AppointmentsKanban
          title=""
          rows={upcoming}
          withDate
          canAct={isDoctor}
          staffId={staff?.id ?? null}
        />
      </div>
    </div>
  );
}
