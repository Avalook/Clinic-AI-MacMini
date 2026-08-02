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
import RosterBell from "../RosterBell";

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
  const apptEndUtc = new Date(
    new Date(apptStartUtc).getTime() + 7 * DAY_MS,
  ).toISOString();
  const WEEK_APPT_SELECT = `
    id, slot_start, status, queue_number, doctor_id, booking_channel,
    patient:patient!clinic_patient_id (
      clinic_patient_id, patient_code, full_name, date_of_birth,
      phone_primary, phone_secondary, gender, ethnicity, nationality, occupation,
      patient_objection, address, guardian_name
    ),
    doctor:staff!doctor_id ( full_name ),
    service:service_type!service_type_id ( name )
  `;

  // Check-in hôm nay (đủ trường hành chính để mở hồ sơ lâm sàng ở cột phải).
  const CHECKIN_SELECT = `
    id, slot_start, status, queue_number, booking_channel,
    patient:patient!clinic_patient_id (
      clinic_patient_id, patient_code, full_name, date_of_birth,
      phone_primary, phone_secondary, gender, ethnicity, nationality, occupation,
      patient_objection, address, guardian_name
    ),
    service:service_type!service_type_id ( name ),
    visit:visit!appointment_id ( checked_in_at )
  `;

  // Trạng thái BN buổi khám hôm nay (chỉ Lễ tân) — đọc visit TẠO HÔM NAY +
  // join patient/bác sĩ/dịch vụ. 3 staff-FK trên visit → phải chỉ rõ
  // attending_doctor_id để PostgREST không nhập nhằng. RLS SELECT cho phép.
  const VISIT_STATUS_SELECT = `
    visit_id, status, checked_in_at, created_at, exam_completed_at,
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
  ] = await Promise.all([
    supabase
      .from("staff_task")
      .select("*", { count: "exact", head: true })
      .eq("status", "PENDING"),
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
    supabase
      .from("appointment")
      .select(WEEK_APPT_SELECT)
      .gte("slot_start", apptStartUtc)
      .lt("slot_start", apptEndUtc)
      // Bỏ lịch ĐÃ HỦY / không đến / BS từ chối khỏi bảng "Lịch hẹn khám" — hủy
      // xong thì ẩn khỏi lưới + trả chỗ về ô trống "+ Đặt lịch vào đây".
      .not("status", "in", "(CANCELLED,NO_SHOW,DOCTOR_DECLINED)")
      .order("slot_start", { ascending: true })
      .limit(500),
    showCheckin
      ? supabase
          .from("appointment")
          .select(CHECKIN_SELECT)
          .gte("slot_start", dayStart)
          .lt("slot_start", dayEnd)
          // GIỮ luôn BN đã CHECKED_IN + đã COMPLETED — không xoá khỏi danh sách
          // sau khi check-in / khám xong, để lễ tân thấy ai đã đến cả ngày.
          .in("status", [
            "SCHEDULED",
            "CSKH_CONFIRMED",
            "CONFIRMED",
            "CHECKED_IN",
            "COMPLETED",
          ])
          .order("slot_start", { ascending: true })
          .limit(300)
      : Promise.resolve({ data: [] }),
    isReception
      ? supabase
          .from("visit")
          .select(VISIT_STATUS_SELECT)
          .gte("created_at", dayStart)
          .lt("created_at", dayEnd)
          .order("created_at", { ascending: true })
          .limit(300)
      : Promise.resolve({ data: [], error: null }),
  ]);
  // visit embed (1-nhiều phía appointment) trả MẢNG → phẳng hoá thành checked_in_at
  // để compareQueue dùng THỨ TỰ GỌI ưu tiên (Model ②) cho người đã check-in.
  const checkinRows = (
    (checkinRes.data as
      | (HomeCheckinRow & { visit?: { checked_in_at: string | null }[] | null })[]
      | null) ?? []
  ).map((r) => ({
    ...r,
    checked_in_at: r.visit?.[0]?.checked_in_at ?? null,
  })) as HomeCheckinRow[];

  // Board trạng thái buổi khám: nếu select đầy đủ LỖI (DB chinh "gần rỗng" có
  // thể CHƯA apply mig 058 exam_completed_at, hoặc thiếu quan hệ appointment FK)
  // → KHÔNG để bảng trắng câm. Rơi xuống select TỐI THIỂU (không exam_completed_at,
  // không join appointment), rồi lấy appointment.status riêng theo appointment_id.
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
  const progress =
    (await fetchFromBackend<VisitProgressRow[]>(
      `/api/v1/visits/progress?from=${apptDates[0]}&to=${apptDates[apptDates.length - 1]}`,
    )) ?? [];
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
  type RawAppt = Omit<WeekApptRow, "phan_loai">;
  const weekApptRows = (weekApptRes.data as RawAppt[] | null) ?? [];

  // "Phân loại khám" (Tái khám / Khám lần đầu) — suy từ lịch hẹn: BN có lịch hẹn
  // nào SỚM HƠN lịch này → Tái khám; nếu đây là lịch sớm nhất của BN → Khám lần
  // đầu. (DB chưa có cột phân loại riêng; đây là suy luận, không phải bịa số.)
  const patientIds = [
    ...new Set(
      weekApptRows
        .map((a) => a.patient?.clinic_patient_id)
        .filter((x): x is string => !!x),
    ),
  ];
  const earliestByPatient = new Map<string, number>();
  if (patientIds.length) {
    const { data: prior } = await supabase
      .from("appointment")
      .select("clinic_patient_id, slot_start")
      .in("clinic_patient_id", patientIds);
    for (const r of (prior as
      | { clinic_patient_id: string; slot_start: string }[]
      | null) ?? []) {
      const t = new Date(r.slot_start).getTime();
      const cur = earliestByPatient.get(r.clinic_patient_id);
      if (cur === undefined || t < cur)
        earliestByPatient.set(r.clinic_patient_id, t);
    }
  }
  const phanLoaiOf = (a: RawAppt): string => {
    const pid = a.patient?.clinic_patient_id;
    if (!pid) return "";
    const earliest = earliestByPatient.get(pid);
    if (earliest === undefined) return "";
    return new Date(a.slot_start).getTime() > earliest
      ? "Tái khám"
      : "Khám lần đầu";
  };

  // Bác sĩ TRỰC CA từng ngày của TUẦN LỊCH HẸN (weekAppt ≠ weekRoster!) — nuôi
  // các nhóm bác sĩ + ô xanh "đặt vào đây" trong bảng Lịch hẹn khám. Đọc thẳng
  // work_roster theo work_date (không lọc week_start vì 2 bảng tuần độc lập).
  const dutyByDate: DutyByDate = {};
  {
    const { data: duty } = await supabase
      .from("work_roster")
      .select("work_date, staff_id, staff_name")
      .in("work_date", apptDates)
      .eq("station", "LICH_KHAM")
      .eq("status", "APPROVED")
      .not("staff_id", "is", null);
    for (const r of (duty as
      | { work_date: string; staff_id: string; staff_name: string | null }[]
      | null) ?? []) {
      const list = dutyByDate[r.work_date] ?? [];
      if (!list.some((d) => d.id === r.staff_id)) {
        list.push({ id: r.staff_id, name: r.staff_name ?? "" });
      }
      dutyByDate[r.work_date] = list;
    }
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
      .map((a) => ({
        ...a,
        phan_loai: phanLoaiOf(a),
        has_vitals: vitalsRecorded.has(a.id),
      }));
    return { date, items };
  });

  const homeTitle = isReception ? "Tổng quan tiếp nhận" : greet(role, staff);
  const homeSubtitle = isReception
    ? "Theo dõi lịch hẹn, tình trạng buổi khám và lịch trực trong cùng một không gian."
    : `Hôm nay · ${fmtDate(new Date())}`;

  return (
    <div className="mx-auto max-w-[1540px] space-y-5">
      <RosterBell />
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
