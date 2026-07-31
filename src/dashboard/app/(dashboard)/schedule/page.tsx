// Lịch làm việc — 2 BẢNG MA TRẬN tuần (đồng bộ mọi vai trò: cùng layout với
// "Lịch làm việc · tuần này" trên Trang chủ — ngày × trạm, gom theo tầng):
//  1. "Lịch làm việc" (read-only): chỉ ca ĐÃ DUYỆT — lịch chung chính thức.
//  2. "Đăng ký lịch làm việc" (tương tác): click 1 ô → tự đăng ký ca CỦA MÌNH,
//     thấy luôn đăng ký của người khác + trạng thái để tự liệu. Đăng ký → PENDING.
//  - Quản lý: thêm nút "Sửa lịch" + hàng đợi "Chờ duyệt" (duyệt / từ chối kèm lý do).
// Ghi qua /api/roster (đăng ký/duyệt) hoặc /schedule/edit (quản lý xếp tay).

import Link from "next/link";
import { getSupabaseServer } from "../../../lib/supabase-server";
import {
  getClinicRole,
  getClinicStaffId,
  getActiveStaff,
} from "../../../lib/clinic-session";
import { isOpsAdmin, isAdminRole } from "../../../lib/roles";
import {
  fmtDayMonth,
  weekDates,
  weekStartOf,
  shiftWeek,
  currentWeekStartVn,
} from "../../../lib/roster";
import WorkRosterTable, {
  type RosterRow,
} from "../home/WorkRosterTable";
import RosterRegisterTable, {
  type RegisterRow,
} from "./RosterRegisterTable";

export const dynamic = "force-dynamic";

// Row kèm id + trạng thái để bảng đăng ký phân biệt ca của mình & lý do từ chối.
interface RosterRowWithId extends RosterRow {
  id: string;
  reject_reason: string | null;
  staff_id: string | null;
  status: "PENDING" | "APPROVED" | "REJECTED";
}

export default async function SchedulePage({
  searchParams,
}: {
  searchParams: Promise<{ week?: string }>;
}) {
  const { week: rawWeek } = await searchParams;
  const week = rawWeek ? weekStartOf(rawWeek) : currentWeekStartVn();
  const dates = weekDates(week);

  const role = await getClinicRole();
  const isAdmin = isOpsAdmin(role); // ops admin (gồm Trưởng ca): nút "Sửa lịch".
  const isApprover = isAdminRole(role); // CHỈ Quản lý: duyệt/từ chối ca trong popup.
  // Lấy staff_id cho MỌI vai (kể cả admin) để bảng đăng ký nhận diện ca của mình.
  const myStaffId = await getClinicStaffId();
  const myStaff = await getActiveStaff();
  const myStaffName = myStaff?.full_name ?? myStaff?.short_name ?? undefined;

  // Lấy TOÀN BỘ phân công của tuần (cho mọi vai trò) → bảng ma trận đồng bộ với
  // trang chủ. Form "Đăng ký ca của tôi" lọc client-side theo staff_id.
  const supabase = await getSupabaseServer();
  const { data } = await supabase
    .from("work_roster")
    .select(
      "id, work_date, shift, station, staff_id, staff_name, status, reject_reason",
    )
    .eq("week_start", week)
    .order("sort", { ascending: true });
  const rows = (data as RosterRowWithId[] | null) ?? [];

  // Lịch chung CHỈ hiện ca đã duyệt. Ca PENDING/REJECTED không lọt vào bảng.
  const approvedRows = rows.filter((r) => r.status === "APPROVED");

  const weekLabel = `${fmtDayMonth(dates[0])} – ${fmtDayMonth(dates[6])}`;
  const navHref = (w: string) => `/schedule?week=${w}`;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-ink">Lịch làm việc</h1>
        </div>
        {isAdmin && (
          <Link
            href={`/schedule/edit?week=${week}`}
            className="rounded-lg bg-brand-600 px-3.5 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
          >
            Sửa lịch
          </Link>
        )}
      </header>

      {/* Điều hướng tuần */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-white px-3 py-2">
        <Link
          href={navHref(shiftWeek(week, -1))}
          className="rounded-md border border-line px-3 py-1.5 text-sm text-ink-soft transition-colors hover:bg-surface-sunken"
        >
          ← Tuần trước
        </Link>
        <span className="text-sm font-medium text-ink">Tuần {weekLabel}</span>
        <Link
          href={navHref(shiftWeek(week, 1))}
          className="rounded-md border border-line px-3 py-1.5 text-sm text-ink-soft transition-colors hover:bg-surface-sunken"
        >
          Tuần sau →
        </Link>
      </div>

      {/* BẢNG 1 — Lịch làm việc chính thức (chỉ ca ĐÃ DUYỆT). */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-ink">Lịch làm việc</h2>
        <WorkRosterTable dates={dates} rows={approvedRows} />
      </section>

      {/* BẢNG 2 — Đăng ký lịch làm việc (tương tác: click ô → tự đăng ký ca;
          Quản lý duyệt / từ chối ngay trong popup của ô). */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-ink">
          Đăng ký lịch làm việc
        </h2>
        <p className="text-xs text-ink-muted">
          Bấm vào ô (ngày × vị trí) để đăng ký ca của bạn. Ca đăng ký ở trạng thái
          “Chờ duyệt” đến khi quản lý xác nhận; bạn cũng thấy đăng ký của người khác
          để tự liệu lịch.
        </p>
        <RosterRegisterTable
          key={week}
          weekStart={week}
          dates={dates}
          myStaffId={myStaffId}
          myStaffName={myStaffName}
          isApprover={isApprover}
          rows={rows.map(
            (r): RegisterRow => ({
              id: r.id,
              work_date: r.work_date,
              station: r.station,
              shift: r.shift as "FULL" | "SANG" | "CHIEU",
              staff_id: r.staff_id,
              staff_name: r.staff_name ?? "",
              status: r.status,
              reject_reason: r.reject_reason,
            }),
          )}
        />
      </section>
    </div>
  );
}
