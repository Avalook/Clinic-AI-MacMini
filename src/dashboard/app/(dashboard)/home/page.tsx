// Trang chủ — ĐỒNG BỘ cho mọi vai trò. Giữ ĐÚNG 4 khối:
//  1. Lời chào (chức danh + tên) + ngày hôm nay
//  2. 3 ô số: Việc đang chờ làm · BN mới đăng ký hôm nay · Lịch chờ xác nhận
//  3. Ca trực hôm nay của bạn (từ work_roster)
//
// (Khối "2 mục" Lịch hẹn/Lịch làm việc + "Lối tắt" cũ đã bỏ/ẩn theo yêu cầu —
//  comment "Lối tắt" giữ ở cuối file để dùng lại nếu cần.)

import StatCard from "../StatCard";
import { getSupabaseServer } from "../../../lib/supabase-server";
import {
  getClinicRole,
  getActiveStaff,
  getClinicStaffId,
} from "../../../lib/clinic-session";
import { type ClinicRole, canCheckin, canWriteClinical } from "../../../lib/roles";
import HomeCheckin, { type HomeCheckinRow } from "./HomeCheckin";
import type { ActiveStaff } from "../../../lib/clinic-session";
import { vnTodayRangeUtc, fmtDate, vnLocalToUtcISO } from "../../../lib/datetime";
import { fetchFromBackend } from "../../../lib/backend-proxy";
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

// Bỏ tiền tố chức danh khỏi tên ("BS Thành" → "Thành", "ĐD Hà Vũ" → "Hà Vũ").
function cleanName(name: string): string {
  return name.replace(/^(BS\s*SA|BS|ĐD|TL)\s+/i, "").trim();
}

function greet(role: ClinicRole | null, staff: ActiveStaff | null): string {
  if (!role || !staff) return "Trang chủ";
  return `Xin chào ${GREET_LABEL[role]} ${cleanName(staff.full_name ?? staff.short_name)}`;
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ weekAppt?: string; weekRoster?: string }>;
}) {
  const supabase = await getSupabaseServer();
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
  const { startUtc: dayStart, endUtc: dayEnd } = vnTodayRangeUtc();

  // 2 bảng có tuần ĐỘC LẬP: weekAppt cho Lịch hẹn khám, weekRoster cho Lịch làm
  // việc — bấm nút bảng nào CHỈ đổi tuần bảng đó (không kéo theo bảng kia).
  const { weekAppt: rawWeekAppt, weekRoster: rawWeekRoster } = await searchParams;
  const weekAppt = rawWeekAppt ? weekStartOf(rawWeekAppt) : currentWeekStartVn();
  const weekRoster = rawWeekRoster
    ? weekStartOf(rawWeekRoster)
    : currentWeekStartVn();
  const apptDates = weekDates(weekAppt);
  const rosterDates = weekDates(weekRoster);
  const apptStartUtc = vnLocalToUtcISO(weekAppt, "00:00");
  // Trạng thái BN buổi khám hôm nay (chỉ Lễ tân) — đọc visit TẠO HÔM NAY +
  // join patient/bác sĩ/dịch vụ. 3 staff-FK trên visit → phải chỉ rõ
  // attending_doctor_id để PostgREST không nhập nhằng. RLS SELECT cho phép.
  const VISIT_STATUS_SELECT = `
    visit_id, status, checked_in_at, created_at, finalized_at,
    patient:patient!clinic_patient_id ( full_name, patient_code ),
    doctor:staff!attending_doctor_id ( full_name ),
    service:service_type!service_type_id ( name ),
    appointment:appointment!appointment_id ( status )
  `;

  // 3 ô số + ca trực hôm nay + roster tuần + lịch hẹn tuần + check-in hôm nay.
  const [
    taskRes,
    newPatientRes,
    pendingApptRes,
    rosterRes,
    weekApptRes,
    checkinRes,
    visitStatusRes,
    dutyRes,
    progressRes,
  ] = await Promise.all([
    supabase
      .from("work_item")
      .select("*", { count: "exact", head: true })
      .in("status", ["PENDING", "IN_PROGRESS"]),
    supabase
      .from("patient")
      .select("*", { count: "exact", head: true })
      .gte("created_at", dayStart)
      .lt("created_at", dayEnd),
    supabase
      .from("appointment")
      .select("*", { count: "exact", head: true })
      .eq("status", "SCHEDULED")
      .gte("slot_start", dayStart)
      .lt("slot_start", dayEnd),
    supabase
      .from("work_roster")
      .select("work_date, station, staff_name, shift")
      .eq("week_start", weekRoster)
      .eq("status", "APPROVED"), // chỉ ca đã duyệt mới lên lịch chung trang chủ
    // LỊCH HẸN TUẦN — nay do FastAPI trả, KÈM SẴN phan_loai.
    //
    // Trước đây chỗ này là một truy vấn PostgREST, rồi bên dưới còn một truy
    // vấn NỮA (không giới hạn) để đọc toàn bộ lịch sử hẹn của từng bệnh nhân
    // chỉ để tính "Tái khám hay Khám lần đầu". Hai vòng mạng nối tiếp cho một
    // chuỗi ký tự mỗi dòng, và cùng một luật ấy còn được chép lại ở
    // tasks/page.tsx — hai bản sao chờ ngày lệch nhau.
    //
    // Đã đối chiếu với đường cũ trên dữ liệu prod trước khi đổi: 46 dòng qua 13
    // tuần, mọi trường giống hệt (xem week_appointments_service.py).
    fetchFromBackend<{ items: WeekApptRow[] }>(
      `/api/v1/appointments/week?week_start=${weekAppt}`,
    ),
    // Check-in hôm nay — ĐỌC QUA BACKEND, không đọc thẳng Supabase nữa.
    //
    // Không phải để gọn: thứ tự gọi bây giờ do backend tính (call_order), và
    // một truy vấn Supabase thì không mang con số đó về. Để nguyên đường cũ thì
    // màn này sẽ IM LẶNG mất thứ tự ưu tiên — mọi dòng call_order rỗng, phép
    // xếp thành vô tác dụng, và không có lỗi nào hiện ra.
    //
    // GIỮ luôn BN đã CHECKED_IN + đã COMPLETED để lễ tân thấy ai đã đến cả ngày.
    showCheckin
      ? fetchFromBackend<{ items: HomeCheckinRow[] }>(
          `/api/v1/appointments/doctor-board?start=${encodeURIComponent(dayStart)}` +
            `&end=${encodeURIComponent(dayEnd)}` +
            `&statuses=SCHEDULED,CSKH_CONFIRMED,CONFIRMED,CHECKED_IN,COMPLETED`,
        )
      : Promise.resolve({ items: [] as HomeCheckinRow[] }),
    isReception
      ? supabase
          .from("visit")
          .select(VISIT_STATUS_SELECT)
          .gte("created_at", dayStart)
          .lt("created_at", dayEnd)
          .order("created_at", { ascending: true })
          .limit(300)
      : Promise.resolve({ data: [], error: null }),
    supabase
      .from("work_roster")
      .select("work_date, staff_id, staff_name")
      .in("work_date", apptDates)
      .eq("station", "LICH_KHAM")
      .eq("status", "APPROVED")
      .not("staff_id", "is", null),
    // Cùng lý do với work_roster ngay trên: đầu vào chỉ là `apptDates`, có từ
    // dòng 96. Nó từng nằm sau `await` nên đợi cả khối này xong mới chạy.
    fetchFromBackend<VisitProgressRow[]>(
      `/api/v1/visits/progress?from=${apptDates[0]}&to=${apptDates[apptDates.length - 1]}`,
    ),
  ]);
  // Backend trả `checked_in_at` PHẲNG sẵn (doctor_board_service chọn một lượt
  // khám có thứ tự trong SQL). Bước phẳng hoá cũ lấy `visit[0]` từ một mảng
  // KHÔNG có thứ tự — tức là chọn ngẫu nhiên khi một lịch có nhiều lượt.
  //
  // `?? []` khi backend không với tới: KHÔNG phải bước lùi — đường Supabase cũ
  // cũng cho ra danh sách rỗng khi truy vấn lỗi. Nhưng nó vẫn là một khoảng
  // trắng nói dối ("hôm nay không ai đến" khi thật ra là "không hỏi được"), và
  // đáng sửa cùng lúc cho cả trang, không phải riêng khối này.
  const checkinRows = checkinRes?.items ?? [];

  // Board trạng thái buổi khám: nếu select đầy đủ LỖI → KHÔNG để bảng trắng
  // câm. Rơi xuống select TỐI THIỂU (không join appointment), rồi lấy
  // appointment.status riêng theo appointment_id.
  //
  // ĐƯỜNG LÙI NÀY TỪNG LÀ ĐƯỜNG DUY NHẤT. Truy vấn chính đọc
  // `exam_completed_at` — một cột chỉ có trong baseline_schema, mà baseline
  // được ĐÁNH DẤU đã áp chứ chưa bao giờ chạy thật trên prod. Nên select đầy
  // đủ LUÔN lỗi, lần tải nào cũng tốn một vòng mạng ra Seoul cho một câu chắc
  // chắn hỏng, rồi mới đi đường lùi — và cột "thời lượng khám" chưa bao giờ
  // hiện được con số nào.
  //
  // `finalized_at` là cột CÓ THẬT và ĐANG ĐƯỢC GHI: clinical_sign_service đặt
  // nó khi bác sĩ ký bệnh án. Baseline khai cả hai cột cho cùng một việc và
  // không ai từng ghi vào cột thứ hai.
  //
  // Giữ đường lùi lại: nó rẻ, và nó đã một lần cứu màn hình khỏi trắng câm.
  let visitStatusRows = (visitStatusRes.data as VisitStatusRow[] | null) ?? [];
  if (isReception && (visitStatusRes as { error?: unknown }).error) {
    const FALLBACK_SELECT = `
      visit_id, status, checked_in_at, created_at, appointment_id,
      patient:patient!clinic_patient_id ( full_name, patient_code ),
      doctor:staff!attending_doctor_id ( full_name ),
      service:service_type!service_type_id ( name )
    `;
    const { data: fb } = await supabase
      .from("visit")
      .select(FALLBACK_SELECT)
      .gte("created_at", dayStart)
      .lt("created_at", dayEnd)
      .order("created_at", { ascending: true })
      .limit(300);
    const rows = (fb as (VisitStatusRow & { appointment_id?: string })[] | null) ?? [];
    const apptIds = [
      ...new Set(rows.map((r) => r.appointment_id).filter((x): x is string => !!x)),
    ];
    if (apptIds.length) {
      const { data: appts } = await supabase
        .from("appointment")
        .select("id, status")
        .in("id", apptIds);
      const statusById = new Map(
        ((appts as { id: string; status: string }[] | null) ?? []).map((a) => [
          a.id,
          a.status,
        ]),
      );
      for (const r of rows) {
        r.appointment = { status: statusById.get(r.appointment_id ?? "") ?? null };
      }
    }
    visitStatusRows = rows;
  }

  // Lịch bị HỦY / KHÔNG ĐẾN sau khi đã check-in vẫn còn visit (OPEN/IN_PROGRESS)
  // → bảng "Trạng thái BN buổi khám" hiển thị "Đang khám" mãi + đếm sai. Lọc bỏ
  // các lượt mà appointment đã CANCELLED/NO_SHOW (KHÔNG xóa visit — giữ data lâm
  // sàng nếu đã nhập; chỉ ẩn khỏi bảng theo dõi buổi khám).
  visitStatusRows = visitStatusRows.filter((v) => {
    const s = v.appointment?.status ?? null;
    return s !== "CANCELLED" && s !== "NO_SHOW";
  });

  // Tiến trình mỗi lượt khám (đã đo sinh hiệu chưa, đã thu những khâu nào) lấy
  // từ FastAPI — ROLE-02. Trang này mở cho MỌI vai, kể cả Lễ tân/Thu ngân; trước
  // đây nó đọc thẳng clinical_record + prescription bằng phiên người dùng, nên
  // policy đọc bệnh án buộc phải mở cho cả những vai không làm lâm sàng. Backend
  // trả về CỜ, không trả nội dung bệnh án.
  const progress = progressRes ?? [];
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
    }
  }

  const cards = [
    { label: "Việc đang chờ làm", value: taskRes.count ?? 0 },
    { label: "BN mới đăng ký hôm nay", value: newPatientRes.count ?? 0 },
    { label: "Lịch chờ xác nhận", value: pendingApptRes.count ?? 0 },
  ];
  // Gom lịch hẹn theo ngày (tuần này) cho bảng "Lịch hẹn khám".
  const rosterRows = (rosterRes.data as RosterRow[] | null) ?? [];
  // Backend trả sẵn phan_loai, nên không còn `RawAppt` (kiểu "thiếu phan_loai")
  // và không còn bước gắn thêm ở dưới. `?? []` là khi backend không trả lời —
  // lưới hiện trống, giống mọi nguồn khác của trang này.
  const weekApptRows: WeekApptRow[] = weekApptRes?.items ?? [];

  // Bác sĩ TRỰC CA từng ngày của TUẦN LỊCH HẸN (weekAppt ≠ weekRoster!) — nuôi
  // các nhóm bác sĩ + ô xanh "đặt vào đây" trong bảng Lịch hẹn khám.
  //
  // Truy vấn này TỪNG nằm ở đây, sau `await` — tức là nó đợi cả Promise.all
  // xong rồi mới bắt đầu, thêm một vòng mạng (~80ms) vào mọi lần mở trang. Nó
  // không có lý do gì để đợi: đầu vào duy nhất là `apptDates`, tính ở dòng 96
  // từ tham số URL, trước Promise.all cả trăm dòng.
  const dutyByDate: DutyByDate = {};
  for (const r of (dutyRes.data as
    | { work_date: string; staff_id: string; staff_name: string | null }[]
    | null) ?? []) {
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

  const homeTitle = isReception ? "Tổng quan tiếp nhận" : greet(role, staff);
  const homeSubtitle = isReception
    ? "Theo dõi lịch hẹn, tình trạng buổi khám và lịch trực trong cùng một không gian."
    : `Hôm nay · ${fmtDate(new Date())}`;

  return (
    <div className="mx-auto max-w-[1540px] space-y-5">
      <header className="rounded-card border border-line bg-surface px-4 py-4 shadow-card sm:px-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-brand-700">
          {isReception ? "Lễ tân" : "Không gian làm việc"}
        </p>
        <h1 className="mt-1 text-xl font-semibold text-ink">{homeTitle}</h1>
        <p className="mt-1 text-sm text-ink-muted">{homeSubtitle}</p>
      </header>

      <section
        aria-label={isReception ? "Tổng quan tiếp nhận" : "Tổng quan ca làm việc"}
        className="grid grid-cols-1 gap-3 sm:grid-cols-3"
      >
        {cards.map((c) => (
          <StatCard key={c.label} label={c.label} value={c.value} />
        ))}
      </section>

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
    </div>
  );
}
