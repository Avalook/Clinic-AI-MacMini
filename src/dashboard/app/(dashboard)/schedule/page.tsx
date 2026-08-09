// Lịch làm việc — 2 BẢNG MA TRẬN tuần (đồng bộ mọi vai trò: cùng layout với
// "Lịch làm việc · tuần này" trên Trang chủ — ngày × trạm, gom theo tầng):
//  1. "Lịch làm việc" (read-only): chỉ ca ĐÃ DUYỆT — lịch chung chính thức.
//  2. "Đăng ký lịch làm việc" (tương tác): click 1 ô → tự đăng ký ca CỦA MÌNH,
//     thấy luôn đăng ký của người khác + trạng thái để tự liệu. Đăng ký → PENDING.
//  - Quản lý: thêm nút "Sửa lịch" + hàng đợi "Chờ duyệt" (duyệt / từ chối kèm lý do).
// Ghi qua /api/roster — bảng đăng ký ở dưới là đường DUY NHẤT để xếp người.

import Link from "next/link";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole } from "../../../lib/clinic-session";
import { isAdminRole, departmentToRole } from "../../../lib/roles";
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
import RosterRegisterTable, {
  type RegisterRow,
  type StaffOpt,
} from "./RosterRegisterTable";
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
  // `sort` rồi `id`: thứ tự trong ô LÀ thứ tự hai hàng con của ngày. Mọi dòng
  // nạp từ Excel đều sort = 0, nên không có chốt thứ hai thì người thứ nhất và
  // thứ hai đổi chỗ cho nhau giữa hai lần tải trang.
  const [{ data }, staffRes, tramRes] = await Promise.all([
    supabase
      .from("work_roster")
      .select(
        "id, work_date, shift, station, staff_id, staff_name, status, reject_reason",
      )
      .eq("week_start", week)
      .order("sort", { ascending: true })
      .order("id", { ascending: true }),
    // Danh sách người để quản lý chọn trong popup, và ma trận phạm vi vị trí.
    // Cả hai chỉ cần khi có ô "+" — nhưng `isAdmin` đã biết từ trên nên đọc
    // luôn ở đây rẻ hơn một vòng mạng nữa từ trình duyệt.
    isAdmin
      ? supabase
          .from("staff")
          .select("id, full_name, short_name, primary_department")
          .eq("is_active", true)
          .order("full_name")
      : Promise.resolve({ data: [] }),
    isAdmin
      ? supabase
          .from("vai_duoc_vao_tram")
          .select("vai, tram_ma")
          .eq("is_active", true)
      : Promise.resolve({ data: [] }),
  ]);
  const rows = (data as RosterRowWithId[] | null) ?? [];

  // Nhân viên xếp được: bỏ dòng có `primary_department` không phải chức danh
  // hợp lệ (không biết vai thì không kiểm được phạm vi vị trí).
  //
  // BỎ LUÔN "Màn hình phòng chờ". Nó là cái tivi treo tường, không phải người,
  // và backend từ chối thẳng nó (`_kiem_pham_vi_tram`). Nó lại chưa khai vị trí
  // nào trong `vai_duoc_vao_tram`, nên nhánh "chưa khai thì cho qua" bên dưới
  // sẽ mời nó vào MỌI trạm — đúng kiểu mời một lựa chọn rồi lưu mới báo lỗi.
  const staffOptions: StaffOpt[] = (
    (staffRes.data as
      | {
          id: string;
          full_name: string;
          short_name: string | null;
          primary_department: string | null;
        }[]
      | null) ?? []
  )
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

  // Chức danh → mã trạm. CÙNG bảng mà backend dùng để từ chối, nên popup không
  // thể mời một người rồi lưu mới báo lỗi.
  const tramTheoVai: Record<string, string[]> = {};
  for (const t of ((tramRes.data as { vai: string; tram_ma: string }[] | null) ??
    [])) {
    (tramTheoVai[t.vai] ??= []).push(t.tram_ma);
  }

  // TÊN NGƯỜI LẤY TỪ MỘT NGUỒN DUY NHẤT.
  //
  // `work_roster.staff_name` là chuỗi TỰ DO nạp từ file Excel "BẢNG LÀM VIỆC",
  // nên cùng một người hiện ra mỗi chỗ một kiểu: "BS THÀNH" ở hàng này,
  // "Bác sĩ · BSNT. Lê Thiệu Quyết" ở hàng kia. Người đọc bảng không biết hai
  // dòng ấy có phải một người hay không.
  //
  // Dòng nào có `staff_id` thì lấy tên từ `staff.full_name` rồi cho qua
  // doctorName() — cùng cái tên mà lưới đặt lịch và mọi màn khác đang hiện.
  // Dòng KHÔNG có staff_id (nhập tay từ Excel, chưa nối được vào ai) giữ nguyên
  // chuỗi cũ: bịa ra một cái tên chuẩn cho một người chưa xác định được là tệ
  // hơn hiện đúng thứ đang có.
  const staffIds = [...new Set(rows.map((r) => r.staff_id).filter(Boolean))];
  const tenTheoId: Record<string, string> = {};
  if (staffIds.length) {
    const { data: nhanSu } = await supabase
      .from("staff")
      .select("id, full_name")
      .in("id", staffIds as string[]);
    for (const nv of (nhanSu as { id: string; full_name: string }[] | null) ?? []) {
      const ten = doctorName(nv.full_name);
      if (ten) tenTheoId[nv.id] = ten;
    }
  }
  const dongBoTen = <T extends RosterRowWithId>(r: T): T => ({
    ...r,
    staff_name: (r.staff_id && tenTheoId[r.staff_id]) || r.staff_name,
  });

  // Lịch chung CHỈ hiện ca đã duyệt. Ca PENDING/REJECTED không lọt vào bảng.
  const approvedRows = rows.filter((r) => r.status === "APPROVED").map(dongBoTen);

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
        <OfficialRosterTable dates={dates} rows={approvedRows} />
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
              Mỗi ngày có <b>hai hàng</b> — mỗi hàng một người. Bấm dấu <b>+</b>{" "}
              trong ô để chọn người và chọn ca (cả ngày · sáng · chiều). Ca xếp
              ở đây vào thẳng lịch chính thức của tuần.
            </p>
          </div>
          <RosterRegisterTable
            weekStart={week}
            dates={dates}
            rows={rows.map(dongBoTen) as RegisterRow[]}
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
