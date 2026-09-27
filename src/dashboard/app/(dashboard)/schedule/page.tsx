// Lịch làm việc — 2 BẢNG MA TRẬN tuần (đồng bộ mọi vai trò: cùng layout với
// "Lịch làm việc · tuần này" trên Trang chủ — ngày × trạm, gom theo tầng):
//  1. "Lịch làm việc" (read-only): chỉ ca ĐÃ DUYỆT — lịch chung chính thức.
//  2. "Đăng ký lịch làm việc" (tương tác): click 1 ô → tự đăng ký ca CỦA MÌNH,
//     thấy luôn đăng ký của người khác + trạng thái để tự liệu. Đăng ký → PENDING.
//  - Quản lý: thêm nút "Sửa lịch" + hàng đợi "Chờ duyệt" (duyệt / từ chối kèm lý do).
// Ghi qua /api/roster — bảng đăng ký ở dưới là đường DUY NHẤT để xếp người.

import Link from "next/link";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import {
  getQuyenCuaToi,
  getViTriHomNay,
  requireNavAccess,
  vaiLamViec,
} from "../../../lib/clinic-session";
import { isAdminRole, departmentToRole } from "../../../lib/roles";
import {
  fmtDayMonth,
  weekDates,
  weekStartOf,
  shiftWeek,
  currentWeekStartVn,
  viTriTuDb,
} from "../../../lib/roster";
import OfficialRosterTable, {
  type OfficialRosterRow,
} from "./OfficialRosterTable";
import ApDungTuan from "./ApDungTuan";
import RosterRegisterTable, {
  type RegisterRow,
  type StaffOpt,
} from "./RosterRegisterTable";
import type { DongCaRow } from "../home/WorkRosterTable";
import { doctorName } from "../../../lib/doctor-name";
import { getClinicStaffId } from "../../../lib/clinic-session";
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
  // Lego 15 "Lịch làm việc" (27/09/2026). Trước đây trang KHÔNG gác gì — thu
  // lego chỉ mất mục trên thanh bên, gõ URL vẫn vào.
  await requireNavAccess("/schedule");
  const { week: rawWeek } = await searchParams;
  // `?week=` là thứ người dùng gõ được. Ngày không đọc được thì rơi về tuần hiện
  // tại — trang vẫn mở. Trước đây nó ném RangeError và cả trang không vào được.
  const week = (rawWeek ? weekStartOf(rawWeek) : null) ?? currentWeekStartVn();
  const dates = weekDates(week);

  // NGƯỜI XẾP LỊCH = có lego 18 "Cài đặt phòng khám" (quyền
  // `config.clinic.manage`) — ĐÚNG câu backend hỏi (`RosterService._xep_lich`),
  // không phải vai Quản lý (kiểm toán 27/09/2026). Nút bấm được mà backend từ
  // chối tệ hơn không có nút. Máy chủ chưa trả lời quyền → rơi về vai như cũ.
  const quyen = await getQuyenCuaToi();
  const isAdmin =
    quyen !== null
      ? quyen.includes("config.clinic.manage")
      : isAdminRole(await vaiLamViec(isAdminRole));

  // Lấy TOÀN BỘ phân công của tuần (cho mọi vai trò) → bảng ma trận đồng bộ với
  // trang chủ. Form "Đăng ký ca của tôi" lọc client-side theo staff_id.
  // 24/09/2026: đọc qua backend `GET /api/v1/roster/lich-tuan` thay vì tự đọc
  // 5 bảng bằng Supabase. Nhân sự + trạm theo vai chỉ về khi người xem là người
  // xếp lịch (backend quyết); ở đây chỉ còn rút gọn tên để hiển thị.
  const [lich, viTri] = await Promise.all([
    fetchFromBackend<{
      da_ap_dung: boolean;
      dong: (Omit<RosterRowWithId, "staff_name"> & {
        staff_name: string | null;
        ten_chuan: string | null;
      })[];
      dong_ca: DongCaRow[];
      nhan_su: {
        id: string;
        full_name: string;
        short_name: string | null;
        primary_department: string | null;
      }[];
      tram_theo_vai: { vai: string; tram_ma: string }[];
    }>(`/api/v1/roster/lich-tuan?tuan=${encodeURIComponent(week)}`),
    getViTriHomNay(),
  ]);
  const stations = viTriTuDb(viTri?.danh_muc);
  const dong = lich?.dong_ca ?? [];

  const staffOptions: StaffOpt[] = (isAdmin ? (lich?.nhan_su ?? []) : [])
    .filter(
      (s) =>
        departmentToRole(s.primary_department) !== null &&
        s.primary_department !== "DISPLAY",
    )
    .map((s) => ({
      id: s.id,
      name: doctorName(s.full_name) || s.short_name || s.full_name,
      vai: s.primary_department as string,
    }));

  const tramTheoVai: Record<string, string[]> = {};
  for (const t of lich?.tram_theo_vai ?? []) {
    (tramTheoVai[t.vai] ??= []).push(t.tram_ma);
  }

  // Tên chuẩn theo staff_id (dòng nhập tay không nối được ai giữ chuỗi cũ).
  const rowsDongBo = (lich?.dong ?? []).map(({ ten_chuan, ...r }) => ({
    ...r,
    staff_name: (r.staff_id && doctorName(ten_chuan)) || r.staff_name || "",
  })) as RosterRowWithId[];

  const approvedRows = rowsDongBo.filter((r) => r.status === "APPROVED");
  const tuanApDung = lich?.da_ap_dung ?? false;

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
        {/* NÚT "SỬA LỊCH" ĐÃ BỎ cùng trang /schedule/edit (Quang 09/08/2026).
            Xếp người nay làm ngay trong bảng bên dưới — bấm dấu "+" trong ô là
            chọn được người cho đúng trạm, đúng ngày. Giữ thêm một màn thứ hai
            làm cùng việc là hai chỗ ghi vào cùng một bảng, và người dùng phải
            đoán chỗ nào mới là chỗ thật. */}
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
        <OfficialRosterTable
          stations={stations}
          dates={dates}
          rows={approvedRows}
          dong={dong}
        />
      </section>

      {/* BẢNG ĐĂNG KÝ CA — BẬT LẠI, NHƯNG CHỈ CHO QUẢN LÝ (Quang 09/08/2026).

          Nó bị ẩn ngày 07/08 vì lúc ấy nhân viên không còn tự xin ca. Nay quản
          lý cần lại đúng cái ô có dấu "+" để xếp người ngay trong bảng, thay vì
          phải sang màn Sửa lịch riêng.

          CHỈ QUẢN LÝ, và đó không phải lựa chọn thẩm mỹ: đường ghi ở API đã
          siết về Quản lý (ROSTER_ROLES trong config_service.py). Bày ô "+" cho
          vai khác là bày một nút bấm vào sẽ ăn 403 — tệ hơn không có nút. */}
      {isAdmin && (
        <section className="min-w-0 space-y-3 rounded-card border border-line bg-surface p-4 shadow-card">
          <div>
            <h2 className="font-semibold text-ink">Đăng ký / xếp ca</h2>
            <p className="mt-0.5 text-sm text-ink-muted">
              Form y hệt file Excel: hàng là vị trí, cột là ngày và ca. Bấm dấu{" "}
              <b>+</b> trong ô để chọn người. Ô đen là vị trí không làm ca ấy.
              Ca xếp ở đây vào thẳng lịch chính thức của tuần.
            </p>
          </div>
          <RosterRegisterTable
            stations={stations}
            weekStart={week}
            dates={dates}
            rows={rowsDongBo as RegisterRow[]}
            dong={dong}
            myStaffId={await getClinicStaffId()}
            staff={staffOptions}
            tramTheoVai={tramTheoVai}
            isApprover
          />
        </section>
      )}
    </main>
  );
}
