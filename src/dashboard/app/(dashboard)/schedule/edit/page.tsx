// Sửa lịch làm việc — chỉ Quản lý. Nạp tuần + nhân viên + các ô đã phân công,
// rồi giao cho RosterEditor (client) thêm/xoá qua /api/roster.

import Link from "next/link";
import { redirect } from "next/navigation";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getClinicRole } from "../../../../lib/clinic-session";
import { isOpsAdmin, departmentToRole } from "../../../../lib/roles";
import {
  weekStartOf,
  weekDates,
  fmtDayMonth,
  currentWeekStartVn,
  type Shift,
} from "../../../../lib/roster";
import RosterEditor, { type EditorRow } from "./RosterEditor";

export const dynamic = "force-dynamic";

export default async function ScheduleEditPage({
  searchParams,
}: {
  searchParams: Promise<{ week?: string }>;
}) {
  const role = await getClinicRole();
  if (!isOpsAdmin(role)) redirect("/schedule");

  const { week: rawWeek } = await searchParams;
  const week = rawWeek ? weekStartOf(rawWeek) : currentWeekStartVn();
  const dates = weekDates(week);

  const supabase = await getSupabaseServer();
  const [rosterRes, staffRes] = await Promise.all([
    supabase
      .from("work_roster")
      .select("id, work_date, shift, station, staff_id, staff_name")
      .eq("week_start", week)
      .eq("status", "APPROVED") // lưới sửa = lịch chính thức; ca chờ duyệt ở panel /schedule
      .order("work_date", { ascending: true })
      .order("sort", { ascending: true }),
    supabase
      .from("staff")
      .select("id, full_name, short_name, primary_department")
      .eq("is_active", true)
      .order("full_name"),
  ]);

  const rows = (rosterRes.data as EditorRow[] | null) ?? [];
  const staff = (
    (staffRes.data as
      | {
          id: string;
          full_name: string;
          short_name: string | null;
          primary_department: string | null;
        }[]
      | null) ?? []
  ).map((s) => ({
    id: s.id,
    name: s.full_name ?? s.short_name,
    role: departmentToRole(s.primary_department),
  }));

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-[#171717]">Sửa lịch làm việc</h1>
          <p className="text-sm text-[#888888]">
            Tuần {fmtDayMonth(dates[0])} – {fmtDayMonth(dates[6])}. Thêm từng phân
            công (ngày · vị trí · nhân viên).
          </p>
        </div>
        <Link
          href={`/schedule?week=${week}`}
          className="rounded-lg border border-[#e4e4e7] px-3.5 py-1.5 text-sm text-[#4d4d4d] hover:bg-[#f4f4f5]"
        >
          ← Xem lịch
        </Link>
      </header>

      <RosterEditor
        weekStart={week}
        dates={dates}
        staff={staff}
        initialRows={rows as (EditorRow & { shift: Shift })[]}
      />
    </div>
  );
}
