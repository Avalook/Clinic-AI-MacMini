// Trang chủ — ĐỒNG BỘ cho mọi vai trò. Giữ ĐÚNG 4 khối:
//  1. Lời chào (chức danh + tên) + ngày hôm nay
//  2. 3 ô số: Việc đang chờ làm · BN mới đăng ký hôm nay · Lịch chờ xác nhận
//  3. Ca trực hôm nay của bạn (từ work_roster)
//
// (Khối "2 mục" Lịch hẹn/Lịch làm việc + "Lối tắt" cũ đã bỏ/ẩn theo yêu cầu —
//  comment "Lối tắt" giữ ở cuối file để dùng lại nếu cần.)
//
// LÁT 3 (22/08/2026) — HAI ĐỔI LỚN, cùng một lý do "đông người không giật":
//
//  * MỘT vòng gói thay 6 vòng PostgREST + 3 endpoint rời. Trước đây mỗi lần
//    mở trang đi: 3 truy vấn đếm + roster tuần + ca trực + (Lễ tân) bảng
//    trạng thái (kèm truy vấn `staff` phụ và một ĐƯỜNG LÙI hai truy vấn khi
//    select join lỗi) + 3 lời gọi FastAPI. Nay tất cả là MỘT
//    `GET /api/v1/home/bang-dieu-khien` — xem man_trang_chu_service.py.
//
//  * SUSPENSE: lời chào + khung trang hiện NGAY, dữ liệu rót vào sau. Trước
//    đây server đợi đủ mọi truy vấn mới trả byte đầu tiên — bấm nút sidebar
//    lúc hệ đang đông là màn hình đứng trắng vài giây, người trực đọc thành
//    "web treo/quá tải" dù mạng không sao. Khung hiện tức thì nói điều
//    ngược lại: hệ sống, dữ liệu đang tới.

import { Suspense, cache } from "react";
import StatCard from "../StatCard";
import {
  getClinicRole,
  getActiveStaff,
  getClinicStaffId,
} from "../../../lib/clinic-session";
import { type ClinicRole, canCheckin, canWriteClinical } from "../../../lib/roles";
import HomeCheckin, { type HomeCheckinRow } from "./HomeCheckin";
import type { ActiveStaff } from "../../../lib/clinic-session";
import { fmtDate, vnLocalToUtcISO } from "../../../lib/datetime";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import { doctorName } from "../../../lib/doctor-name";
import { currentWeekStartVn, weekDates, weekStartOf } from "../../../lib/roster";
import WeekNav from "../WeekNav";
import WeeklyAppointmentsTable, {
  type ApptDay,
  type WeekApptRow,
  type DutyByDate,
} from "./WeeklyAppointmentsTable";
import WorkRosterTable, { type RosterRow } from "./WorkRosterTable";
import VisitStatusBoard, { type VisitStatusRow } from "./VisitStatusBoard";
import VisitStatusRealtime from "./VisitStatusRealtime";

export const dynamic = "force-dynamic";

const DAY_MS = 24 * 60 * 60 * 1000;

/** Shape of GET /api/v1/visits/progress — flags only, never the note itself. */
interface VisitProgressRow {
  appointment_id: string;
  visit_id: string | null;
  vitals_recorded: boolean;
  has_clinical_record: boolean;
  has_prescription: boolean;
  paid_kinds: string[];
  /** Giờ hai mốc giữa của thanh tiến trình (không có trên bảng `visit`). */
  exam_started_at?: string | null;
  paid_at?: string | null;
}

/** Toàn bộ dữ liệu Trang chủ, một lượt — hình do man_trang_chu_service quyết. */
interface GoiTrangChu {
  so_lieu: {
    viec_dang_cho: number;
    khach_moi_hom_nay: number;
    lich_cho_xac_nhan: number;
  };
  roster: (RosterRow & { ten_staff?: string | null })[];
  truc_ca: { work_date: string; staff_id: string; staff_name: string | null }[];
  trang_thai_kham: VisitStatusRow[];
  tuan_hen: WeekApptRow[];
  checkin: HomeCheckinRow[];
  tien_trinh: VisitProgressRow[];
}

// Chức danh ngắn dùng trong lời chào (vd "Chào bác sĩ Thành").
const GREET_LABEL: Record<ClinicRole, string> = {
  DOCTOR: "bác sĩ",
  ULTRASOUND_DOCTOR: "bác sĩ",
  NURSE_ULTRASOUND: "điều dưỡng",
  TKYK: "thư ký y khoa",
  CSKH: "CSKH",
  MANAGEMENT: "quản lý",
  RECEPTION: "lễ tân",
  CASHIER: "thu ngân",
  CASHIER_THUOC: "thu ngân thuốc",
  CASHIER_DV: "thu ngân dịch vụ",
  TRUONG_CA: "trưởng ca",
  PHARMACIST: "dược sĩ",
  // Không bao giờ chào ai: layout đưa vai này thẳng ra /display.
  DISPLAY: "màn hình",
};

// LỜI CHÀO KHÔNG ĐƯỢC LẶP CHỨC DANH.
//
// Quang 09/08/2026: *"chỉ là xin chào CSKH Diệu Hoa thôi"*. Bản trước ghép
// `GREET_LABEL[role]` vào trước `full_name`, mà `full_name` trên prod đã mang
// sẵn chức danh ("CSKH · Diệu Hoa") — ra "Xin chào CSKH CSKH · Diệu Hoa". Hàm
// cắt tiền tố cũ chỉ biết "BS/ĐD/TL", không biết dấu chấm giữa.
//
// `doctorName` là chỗ đã giải đúng chuyện này cho mọi màn khác — dùng lại nó.
function greet(role: ClinicRole | null, staff: ActiveStaff | null): string {
  if (!role || !staff) return "Trang chủ";
  const goc = staff.full_name ?? staff.short_name;
  const ten = doctorName(goc);
  if (!ten) return "Trang chủ";
  // Chuỗi gốc có dấu chấm giữa nghĩa là nó đã mang chức danh, và doctorName giữ
  // lại chức danh ấy. Chỉ khi tên lưu TRẦN mới ghép chức danh — và ghép từ VAI
  // ĐANG ĐĂNG NHẬP, thứ biết chắc từ phiên, chứ không đoán từ cái tên.
  return `Xin chào ${/[·•]/.test(goc) ? ten : `${GREET_LABEL[role]} ${ten}`}`;
}

/** Một ô ma đứng chỗ trong lúc dữ liệu đang rót — cùng khung với thẻ thật. */
function OMa({ cao }: { cao: string }) {
  return (
    <div
      aria-hidden
      className={`${cao} animate-pulse rounded-card border border-line bg-surface-sunken`}
    />
  );
}

/** Khung chờ của phần dữ liệu — hiện tức thì trong lúc gói đang về. */
function KhungTai({ isReception }: { isReception: boolean }) {
  return (
    <>
      <section
        aria-label="Đang tải số liệu"
        className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-3"
      >
        <OMa cao="h-20" />
        <OMa cao="h-20" />
        <OMa cao="h-20" />
      </section>
      {isReception && <OMa cao="h-40" />}
      <OMa cao="h-72" />
      <OMa cao="h-56" />
    </>
  );
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ weekAppt?: string; weekRoster?: string }>;
}) {
  const role = await getClinicRole();
  const staff = await getActiveStaff();
  const staffId = await getClinicStaffId();
  // Lễ tân KHÔNG cần ô check-in riêng: bảng "Lịch hẹn khám" (WeeklyAppointmentsTable) ĐÃ có
  // cột "Thao tác Check-in" (showActions = canCheckin → gồm RECEPTION) — bấm tên BN mở popup
  // check-in / không-đến ngay trong lịch. Ô HomeCheckin riêng chỉ gây TRÙNG nên ẩn cho Lễ
  // tân; vẫn để cho Quản lý (giữ hành vi cũ). Bảng trạng thái read-only của Lễ tân giữ ở dưới.
  const showCheckin = canCheckin(role) && role !== "RECEPTION";
  // CHỈ Bác sĩ + Điều dưỡng ghi lâm sàng; Lễ tân/QL check-in nhưng xem chỉ-đọc.
  const writeClinical = canWriteClinical(role);
  const isReception = role === "RECEPTION"; // bảng trạng thái buổi khám: chỉ Lễ tân

  // 2 bảng có tuần ĐỘC LẬP: weekAppt cho Lịch hẹn khám, weekRoster cho Lịch làm
  // việc — bấm nút bảng nào CHỈ đổi tuần bảng đó (không kéo theo bảng kia).
  const { weekAppt: rawWeekAppt, weekRoster: rawWeekRoster } = await searchParams;
  // Hai tham số này lấy thẳng từ thanh địa chỉ. Ngày không đọc được thì rơi về
  // tuần hiện tại — TRANG CHỦ PHẢI MỞ ĐƯỢC. Trước đây `weekStartOf` ném
  // RangeError trên chuỗi rác, và server component ném thì cả trang rơi vào
  // error.tsx: một link hỏng là màn hình đầu ngày của cả phòng khám không vào được.
  const weekAppt =
    (rawWeekAppt ? weekStartOf(rawWeekAppt) : null) ?? currentWeekStartVn();
  const weekRoster =
    (rawWeekRoster ? weekStartOf(rawWeekRoster) : null) ?? currentWeekStartVn();

  const homeTitle = isReception ? "Tổng quan tiếp nhận" : greet(role, staff);
  const homeSubtitle = isReception
    ? "Theo dõi lịch hẹn, tình trạng buổi khám và lịch trực trong cùng một không gian."
    : `Hôm nay · ${fmtDate(new Date())}`;

  return (
    <div className="mx-auto max-w-[1540px] space-y-5">
      {/* LỜI CHÀO VÀ BA Ô SỐ TRÊN CÙNG MỘT HÀNG.

          Trước đây chúng là hai thẻ chồng nhau, và thẻ lời chào để trống hết
          nửa bên phải — một khoảng trắng bằng cả ba ô số nằm ngay đầu trang mà
          không mang thông tin gì.

          Trên màn hẹp thì vẫn xuống dòng: ba con số quan trọng hơn việc chúng
          nằm cạnh lời chào.

          Từ Lát 3, phần LỜI CHÀO đứng ngoài Suspense — nó chỉ cần phiên, hiện
          tức thì; ba ô số thuộc phần dữ liệu nên rót vào sau. */}
      <header className="flex flex-col gap-4 rounded-card border border-line bg-surface px-4 py-4 shadow-card sm:px-5 lg:flex-row lg:items-center">
        <div className="lg:w-75 lg:shrink-0">
          <p className="text-label font-semibold uppercase tracking-[0.14em] text-brand-700">
            {isReception ? "Lễ tân" : "Không gian làm việc"}
          </p>
          <h1 className="mt-1 text-xl font-semibold text-ink">{homeTitle}</h1>
          <p className="mt-1 text-sm text-ink-muted">{homeSubtitle}</p>
        </div>

        <Suspense
          fallback={
            <section
              aria-label="Đang tải số liệu"
              className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-3"
            >
              <OMa cao="h-16" />
              <OMa cao="h-16" />
              <OMa cao="h-16" />
            </section>
          }
        >
          <BaOSo
            weekAppt={weekAppt}
            weekRoster={weekRoster}
            isReception={isReception}
          />
        </Suspense>
      </header>

      <Suspense fallback={<KhungTai isReception={isReception} />}>
        <KhoiDuLieu
          role={role}
          staffId={staffId}
          showCheckin={showCheckin}
          writeClinical={writeClinical}
          isReception={isReception}
          weekAppt={weekAppt}
          weekRoster={weekRoster}
        />
      </Suspense>
    </div>
  );
}

// MỘT lời gọi gói cho CẢ trang, nhớ trong phạm vi MỘT lượt dựng.
//
// Hai island Suspense (ba ô số + phần thân) cùng đọc gói này — không khử trùng
// lặp thì thành HAI lời gọi backend giống hệt nhau, tức là tự tay nhân đôi cái
// mình vừa gộp. Dùng `cache()` của React chứ KHÔNG dùng Map module-scope: Map
// theo khoá tuần sẽ CHIA SẺ promise giữa hai người dùng khác nhau đang render
// cùng lúc với cùng cặp tuần — cookie của người gọi trước quyết định dữ liệu
// người gọi sau nhìn thấy (bảng Lễ tân, ô Quản lý). `cache()` tự scope theo
// TỪNG lượt render nên không có đường rò ấy.
const goiTrangChu = cache(
  (weekAppt: string, weekRoster: string): Promise<GoiTrangChu | null> =>
    fetchFromBackend<GoiTrangChu>(
      `/api/v1/home/bang-dieu-khien?week_appt=${weekAppt}&week_roster=${weekRoster}`,
    ),
);

/** Ba ô số trên đầu trang — island nhỏ, rót vào cạnh lời chào. */
async function BaOSo({
  weekAppt,
  weekRoster,
  isReception,
}: {
  weekAppt: string;
  weekRoster: string;
  isReception: boolean;
}) {
  const goi = await goiTrangChu(weekAppt, weekRoster);
  const cards = [
    { label: "Việc đang chờ làm", value: goi?.so_lieu.viec_dang_cho ?? 0 },
    { label: "BN mới đăng ký hôm nay", value: goi?.so_lieu.khach_moi_hom_nay ?? 0 },
    { label: "Lịch chờ xác nhận", value: goi?.so_lieu.lich_cho_xac_nhan ?? 0 },
  ];
  return (
    <section
      aria-label={isReception ? "Tổng quan tiếp nhận" : "Tổng quan ca làm việc"}
      className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-3"
    >
      {cards.map((c) => (
        <StatCard key={c.label} label={c.label} value={c.value} />
      ))}
    </section>
  );
}

/** Phần thân dữ liệu của trang — mọi bảng, sau MỘT lời gọi gói. */
async function KhoiDuLieu({
  role,
  staffId,
  showCheckin,
  writeClinical,
  isReception,
  weekAppt,
  weekRoster,
}: {
  role: ClinicRole | null;
  staffId: string | null;
  showCheckin: boolean;
  writeClinical: boolean;
  isReception: boolean;
  weekAppt: string;
  weekRoster: string;
}) {
  const apptDates = weekDates(weekAppt);
  const rosterDates = weekDates(weekRoster);
  const apptStartUtc = vnLocalToUtcISO(weekAppt, "00:00");

  const goi = await goiTrangChu(weekAppt, weekRoster);
  // Backend im thì các bảng cùng rỗng — phải NÓI RA. Một trang chủ trống trơn
  // trông y hệt "hôm nay chưa có gì", và người trực sẽ tin nó (cùng luật với
  // goiLoi ở màn Quản lý khách hàng, Lát 2).
  const goiLoi = goi === null;

  const checkinRows = showCheckin ? (goi?.checkin ?? []) : [];

  // Bảng trạng thái buổi khám: join đã làm THẲNG trong SQL của backend, nên
  // đường-lùi-hai-truy-vấn cũ (sinh ra vì select join PostgREST từng lỗi cột)
  // không còn đất sống — cột sai giờ là CI đỏ ở test service, không đợi prod.
  //
  // Lịch bị HỦY / KHÔNG ĐẾN sau khi đã check-in vẫn còn visit (OPEN/IN_PROGRESS)
  // → bảng hiển thị "Đang khám" mãi + đếm sai. Lọc bỏ các lượt mà appointment
  // đã CANCELLED/NO_SHOW (KHÔNG xóa visit — giữ data lâm sàng nếu đã nhập; chỉ
  // ẩn khỏi bảng theo dõi buổi khám).
  const visitStatusRows = (goi?.trang_thai_kham ?? []).filter((v) => {
    const s = v.appointment?.status ?? null;
    return s !== "CANCELLED" && s !== "NO_SHOW";
  });

  // Tiến trình mỗi lượt khám (đã đo sinh hiệu chưa, đã thu những khâu nào) từ
  // FastAPI — ROLE-02: backend trả về CỜ, không trả nội dung bệnh án, nên Lễ
  // tân/Thu ngân không cần (và không có) quyền đọc bệnh án.
  const progress = goi?.tien_trinh ?? [];
  const progressByVisit = new Map(
    progress.filter((p) => p.visit_id).map((p) => [p.visit_id as string, p]),
  );

  // Mốc "Đã thanh toán": đã thu ĐỦ mọi khâu PHẢI thu của lượt khám = DỊCH VỤ
  // (luôn có, vì có dịch vụ khám) + THUỐC nếu lượt có đơn thuốc.
  if (isReception && visitStatusRows.length) {
    for (const v of visitStatusRows) {
      const p = progressByVisit.get(v.visit_id);
      const kinds = new Set(p?.paid_kinds ?? []);
      v.paid = kinds.has("dich_vu") && (!p?.has_prescription || kinds.has("thuoc"));
      // Giờ hai mốc giữa của thanh tiến trình. Chúng không nằm trên bảng
      // `visit`, nên lấy từ chính khối tiến trình của gói.
      v.exam_started_at = p?.exam_started_at ?? null;
      v.paid_at = p?.paid_at ?? null;
    }
  }

  // TÊN TRONG BẢNG LỊCH LÀM VIỆC LẤY TỪ `staff`, KHÔNG PHẢI CHUỖI EXCEL.
  //
  // Màn /schedule đã làm bước này từ trước; trang chủ thì không, nên cùng một
  // bảng ở hai nơi hiện hai cách viết tên — và ở đây còn tệ hơn: cột "Số BS"
  // đếm theo staff_id nên nó nói 4 trong khi ô bên cạnh bày 5 cái tên (08/08:
  // "Bác sĩ · BSNT. Lê Thiệu Quyết" và "BS QUYẾT" là MỘT người).
  //
  // Backend join sẵn `ten_staff` (staff.full_name); phép CẮT CHỨC DANH vẫn là
  // việc của `doctorName` phía frontend — luật ấy sống một chỗ, không chép
  // sang Python thành bản thứ hai (đúng cách dongBoTenTrucNhat từng làm,
  // chỉ bớt được truy vấn `staff` phụ).
  const rosterRows: RosterRow[] = (goi?.roster ?? []).map((r) => {
    const ten = r.ten_staff ? doctorName(r.ten_staff) : "";
    return { ...r, staff_name: (r.staff_id && ten) || r.staff_name };
  });

  // Backend trả sẵn phan_loai, nên không còn `RawAppt` (kiểu "thiếu phan_loai")
  // và không còn bước gắn thêm ở dưới.
  const weekApptRows: WeekApptRow[] = goi?.tuan_hen ?? [];

  // Bác sĩ TRỰC CA từng ngày của TUẦN LỊCH HẸN (weekAppt ≠ weekRoster!) — nuôi
  // các nhóm bác sĩ + ô xanh "đặt vào đây" trong bảng Lịch hẹn khám.
  const dutyByDate: DutyByDate = {};
  for (const r of goi?.truc_ca ?? []) {
    const list = dutyByDate[r.work_date] ?? [];
    if (!list.some((d) => d.id === r.staff_id)) {
      list.push({ id: r.staff_id, name: r.staff_name ?? "" });
    }
    dutyByDate[r.work_date] = list;
  }

  // "!" nhắc điều dưỡng điền sinh hiệu chỉ hiện khi lịch đã CHECKED_IN mà CHƯA
  // ghi đủ 3 vital bắt buộc (huyết áp / cân nặng / chiều cao). Luật "đủ 3 vital"
  // nằm trong visit_progress_service, cạnh chỗ có dữ liệu — trang này chỉ nhận
  // cờ, nên Lễ tân không cần (và không còn) quyền đọc bệnh án.
  const vitalsRecorded = new Set(
    progress.filter((p) => p.vitals_recorded).map((p) => p.appointment_id),
  );

  const t0 = new Date(apptStartUtc).getTime();
  const apptDays: ApptDay[] = apptDates.map((date, i) => {
    const s = t0 + i * DAY_MS;
    const e = s + DAY_MS;
    const items = weekApptRows
      .filter((a) => {
        const t = new Date(a.slot_start).getTime();
        return t >= s && t < e;
      })
      // phan_loai đã do backend tính; ở đây chỉ gắn thêm cờ sinh hiệu.
      .map((a) => ({ ...a, has_vitals: vitalsRecorded.has(a.id) }));
    return { date, items };
  });

  return (
    <>
      {goiLoi && (
        <div
          role="alert"
          className="rounded-card border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          Không đọc được dữ liệu trang chủ — backend không trả lời. Các bảng
          bên dưới đang trống vì thế, không phải vì hôm nay không có gì.
        </div>
      )}

      {/* Check-in bệnh nhân — TRÊN Lịch hẹn khám (ĐD/Lễ tân/Quản lý).
          Bấm mở danh sách ngay dưới nút; Lịch hẹn khám tự đẩy xuống. */}
      {showCheckin && (
        <HomeCheckin
          rows={checkinRows}
          staffId={staffId}
          canWriteClinical={writeClinical}
        />
      )}

      {/* Trạng thái BN buổi khám hôm nay — CHỈ Lễ tân, READ-ONLY (theo visit.status).
          Thanh tiến trình kiểu Grab + tự cập nhật liên tục (realtime visit). */}
      {isReception && (
        <section aria-label="Trạng thái buổi khám hôm nay" className="rounded-card border border-line bg-surface p-3 shadow-card sm:p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-ink">
              Trạng thái BN buổi khám hôm nay
            </h2>
            <VisitStatusRealtime />
          </div>
          <VisitStatusBoard rows={visitStatusRows} />
        </section>
      )}

      {/* Lịch hẹn khám — nút tuần RIÊNG (weekAppt), KHÔNG đụng Lịch làm việc. */}
      <section aria-label="Lịch hẹn khám" className="rounded-card border border-line bg-surface p-3 shadow-card sm:p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-ink">
            Lịch hẹn khám (check đặt lịch)
          </h2>
          <WeekNav
            week={weekAppt}
            basePath="/home"
            param="weekAppt"
            others={{ weekRoster }}
          />
        </div>
        <WeeklyAppointmentsTable
          days={apptDays}
          role={role}
          staffId={staffId}
          canWriteClinical={writeClinical}
          dutyByDate={dutyByDate}
        />
      </section>

      {/* Lịch làm việc — nút tuần RIÊNG (weekRoster), KHÔNG đụng Lịch hẹn khám. */}
      <section aria-label="Lịch làm việc" className="rounded-card border border-line bg-surface p-3 shadow-card sm:p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-ink">Lịch làm việc</h2>
          <WeekNav
            week={weekRoster}
            basePath="/home"
            param="weekRoster"
            others={{ weekAppt }}
          />
        </div>
        <WorkRosterTable dates={rosterDates} rows={rosterRows} />
      </section>

      {/*
        ===== TẠM ẨN: "Lối tắt" cũ (giữ lại để dùng sau, đừng xoá) =====
        Lối tắt = các mục nav vai trò được phép, dạng nút lớn:

        const actions = NAV.filter(n => n.href !== "/home" && canSeeNav(role, n.href));
        <section>
          <h2>Lối tắt</h2>
          <div className="grid grid-cols-2 ... lg:grid-cols-4">
            {actions.map(({ href, label, icon: Icon }) => (
              <Link href={href} ...><Icon/> {label}</Link>
            ))}
          </div>
        </section>
        (cần import lại: NAV từ "../nav-items", canSeeNav từ "../../../lib/roles")
      */}
    </>
  );
}
