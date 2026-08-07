// Lịch làm việc — 2 BẢNG MA TRẬN tuần (đồng bộ mọi vai trò: cùng layout với
// "Lịch làm việc · tuần này" trên Trang chủ — ngày × trạm, gom theo tầng):
//  1. "Lịch làm việc" (read-only): chỉ ca ĐÃ DUYỆT — lịch chung chính thức.
//  2. "Đăng ký lịch làm việc" (tương tác): click 1 ô → tự đăng ký ca CỦA MÌNH,
//     thấy luôn đăng ký của người khác + trạng thái để tự liệu. Đăng ký → PENDING.
//  - Quản lý: thêm nút "Sửa lịch" + hàng đợi "Chờ duyệt" (duyệt / từ chối kèm lý do).
// Ghi qua /api/roster (đăng ký/duyệt) hoặc /schedule/edit (quản lý xếp tay).

import Link from "next/link";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole } from "../../../lib/clinic-session";
import { isAdminRole } from "../../../lib/roles";
import {
  fmtDayMonth,
  weekDates,
  weekStartOf,
  shiftWeek,
  currentWeekStartVn,
} from "../../../lib/roster";
import OfficialRosterTable, {
  type OfficialRosterRow,
} from "./OfficialRosterTable";
import ApDungTuan from "./ApDungTuan";
export const dynamic = "force-dynamic";

// Row kèm id + trạng thái để bảng đăng ký phân biệt ca của mình & lý do từ chối.
interface RosterRowWithId extends OfficialRosterRow {
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
  // CHỈ QUẢN LÝ. Trước đây chỗ này dùng isOpsAdmin (gồm cả Trưởng ca) trong khi
  // đường ghi ở API chỉ nhận Quản lý — nên Trưởng ca bấm "Sửa lịch", xếp cho
  // người khác, và dòng ghi rơi vào PENDING cho CHÍNH họ, không hiện lại, KHÔNG
  // BÁO LỖI. Một nút bấm được nhưng không làm gì tệ hơn một nút không có.
  const isAdmin = isAdminRole(role);

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

  // Tuần này đã được quản lý bấm áp dụng chưa. Có dòng trong roster_week = rồi.
  const { data: tuanApDung } = await supabase
    .from("roster_week")
    .select("week_start")
    .eq("week_start", week)
    .maybeSingle();

  const weekLabel = `${fmtDayMonth(dates[0])} – ${fmtDayMonth(dates[6])}`;
  const navHref = (w: string) => `/schedule?week=${w}`;

  return (
    <main className="page-in min-w-0 space-y-5 p-4 lg:p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-ink lg:text-2xl">Lịch làm việc</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Lịch trực do quản lý xếp và áp dụng theo tuần.
          </p>
        </div>
        {isAdmin && (
          <Link
            href={`/schedule/edit?week=${week}`}
            className="rounded-control bg-brand-600 px-4 py-2 text-sm font-medium text-surface hover:bg-brand-700"
          >
            Sửa lịch
          </Link>
        )}
      </header>

      {/* Điều hướng tuần */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-card border border-line bg-surface px-3 py-2 shadow-card">
        <Link
          href={navHref(shiftWeek(week, -1))}
          className="rounded-control border border-line px-3 py-1.5 text-sm text-ink-soft transition-colors hover:bg-surface-sunken"
        >
          ← Tuần trước
        </Link>
        <span className="text-sm font-medium text-ink">Tuần {weekLabel}</span>
        <Link
          href={navHref(shiftWeek(week, 1))}
          className="rounded-control border border-line px-3 py-1.5 text-sm text-ink-soft transition-colors hover:bg-surface-sunken"
        >
          Tuần sau →
        </Link>
      </div>

      <ApDungTuan
        weekStart={week}
        daApDung={Boolean(tuanApDung)}
        laQuanLy={isAdmin}
        soCa={approvedRows.length}
      />

      {/* BẢNG 1 — Lịch làm việc chính thức (chỉ ca ĐÃ DUYỆT). */}
      <section className="min-w-0 space-y-3 rounded-card border border-line bg-surface p-4 shadow-card">
        <h2 className="font-semibold text-ink">Lịch làm việc chính thức</h2>
        <OfficialRosterTable dates={dates} rows={approvedRows} />
      </section>

      {/* BẢNG ĐĂNG KÝ CA — TẠM ẨN (Quang, 07/08/2026).

          Quản lý tự xếp lịch cho mọi người trong màn Sửa lịch rồi bấm áp dụng;
          nhân viên chỉ xem lịch chính thức ở trên. Nên ô "+" để tự xin ca không
          còn nghĩa.

          ẨN, KHÔNG XOÁ. `RosterRegisterTable` và luồng duyệt PENDING vẫn còn
          nguyên trong repo để mở lại khi phòng khám cần đường xin đổi ca. Đường
          ghi ở API đã siết về Quản lý (ROSTER_ROLES trong config_service.py) —
          ẩn giao diện mà để hở API là ai cũng còn POST thẳng vào được. */}
    </main>
  );
}
