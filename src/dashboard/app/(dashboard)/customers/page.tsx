// "Thông tin khách hàng" — danh bạ khách (master-detail) KÈM lịch hẹn sắp tới.
// Server đọc patient qua Supabase RLS; lọc theo NGÀY TẠO (created_at) hoặc NGÀY
// HẸN (slot_start) để biết khách thuộc ngày/tuần nào (feedback 05/06). client
// (CustomersView) lo chọn + bôi hồng.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess, getClinicRole } from "../../../lib/clinic-session";
import { canWriteIntake, canManageAppt } from "../../../lib/roles";
import { unaccentVi } from "../../../lib/validation";
import type { EditableAppt } from "./AppointmentEditModal";
import {
  vnTodayRangeUtc,
  vnMonthStartUtc,
  vnLocalToUtcISO,
  VN_TZ,
} from "../../../lib/datetime";
import { currentWeekStartVn, shiftWeek } from "../../../lib/roster";
import type { DongLichSu } from "./GhiTuongTac";
import CustomersView, {
  type CustomerRow,
  type ApptInfo,
  type Opt,
  type Period,
  type ByDim,
} from "./CustomersView";
import { listBookableDoctors } from "../../../lib/doctors-server";

export const dynamic = "force-dynamic";

/** Đầu tháng SAU theo giờ VN, dạng UTC ISO (chặn cuối cửa sổ "Tháng này"). */
function vnNextMonthStartUtc(): string {
  const ymd = new Date().toLocaleDateString("en-CA", {
    timeZone: VN_TZ,
  });
  const [y, m] = ymd.split("-").map(Number);
  const ny = m === 12 ? y + 1 : y;
  const nm = m === 12 ? 1 : m + 1;
  return new Date(
    `${ny}-${String(nm).padStart(2, "0")}-01T00:00:00+07:00`,
  ).toISOString();
}

/** [start,end) UTC cho kỳ lọc theo giờ VN; null = "Tất cả". */
function windowFor(period: Period): { start: string; end: string } | null {
  if (period === "today") {
    const { startUtc, endUtc } = vnTodayRangeUtc();
    return { start: startUtc, end: endUtc };
  }
  if (period === "week") {
    const ws = currentWeekStartVn();
    return {
      start: vnLocalToUtcISO(ws, "00:00"),
      end: vnLocalToUtcISO(shiftWeek(ws, 1), "00:00"),
    };
  }
  if (period === "month") {
    return { start: vnMonthStartUtc(), end: vnNextMonthStartUtc() };
  }
  return null;
}

/** Supabase join trả object HOẶC array (tuỳ quan hệ) — lấy phần tử đầu. */
function pick1<T>(v: T | T[] | null | undefined): T | null {
  if (!v) return null;
  return Array.isArray(v) ? (v[0] ?? null) : v;
}

const SELECT = `
  clinic_patient_id, patient_code, full_name, date_of_birth, birth_year,
  phone_primary, phone_secondary, gender, ethnicity, nationality,
  occupation, patient_objection, address, guardian_name, location_id, created_at,
  van_de_di_kham, linh_vuc
`;

export default async function CustomersPage({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string;
    period?: string;
    by?: string;
    selected?: string;
  }>;
}) {
  await requireNavAccess("/customers");
  const role = await getClinicRole();
  // CSKH / Lễ tân / Quản lý: được SỬA thông tin hành chính ngay trong panel.
  const canEdit = canWriteIntake(role);
  // CSKH / Quản lý / Trưởng ca: được ĐỔI / HỦY lịch hẹn (bấm ô "Lịch hẹn sắp tới").
  const canManage = canManageAppt(role);
  const sp = await searchParams;
  const q = (sp.q ?? "").trim();
  const period: Period = (["today", "week", "month", "all"].includes(
    sp.period ?? "",
  )
    ? sp.period
    : "all") as Period;
  const by: ByDim = sp.by === "appt" ? "appt" : "created";
  const selected = (sp.selected ?? "").trim() || null;
  const win = windowFor(period);

  const supabase = await getSupabaseServer();

  // Lọc THEO NGÀY HẸN: tìm khách có lịch trong cửa sổ trước → lấy danh sách id.
  // BỎ lịch đã hủy/không đến/BS từ chối — hủy lịch xong khách không còn "có hẹn".
  const DEAD_STATUSES = "(CANCELLED,NO_SHOW,DOCTOR_DECLINED)";
  let apptFilterIds: string[] | null = null;
  if (by === "appt" && win) {
    const { data: inWin } = await supabase
      .from("appointment")
      .select("clinic_patient_id")
      .gte("slot_start", win.start)
      .lt("slot_start", win.end)
      .not("clinic_patient_id", "is", null)
      .not("status", "in", DEAD_STATUSES)
      .limit(3000);
    apptFilterIds = [
      ...new Set((inWin ?? []).map((a) => a.clinic_patient_id as string)),
    ];
  }

  // Tìm tên KHÔNG phân biệt dấu (D11): cộng thêm điều kiện trên cột
  // full_name_unaccent (migration 039 — bỏ dấu + thường). useUnaccent=false để
  // fallback nếu cột chưa migrate (KHÔNG đổi DB, chỉ tái dùng cột sẵn có).
  const t = q ? q.replace(/[,()%*]/g, " ").trim() : "";
  const buildPatientQuery = (useUnaccent: boolean) => {
    let query = supabase
      .from("patient")
      .select(SELECT)
      .order("created_at", { ascending: false })
      .limit(300);
    if (by === "created" && win) query = query.gte("created_at", win.start);
    if (by === "appt" && apptFilterIds) {
      // Rỗng → sentinel để .in() không lỗi và trả 0 dòng.
      query = query.in(
        "clinic_patient_id",
        apptFilterIds.length
          ? apptFilterIds
          : ["00000000-0000-0000-0000-000000000000"],
      );
    }
    if (t) {
      const ors = [
        `full_name.ilike.%${t}%`,
        `patient_code.ilike.%${t}%`,
        `phone_primary.ilike.%${t}%`,
      ];
      if (useUnaccent) {
        ors.push(`full_name_unaccent.ilike.%${unaccentVi(t)}%`);
      }
      query = query.or(ors.join(","));
    }
    return query;
  };

  const [patRes, locRes, svcRes, docRes] = await Promise.all([
    buildPatientQuery(true),
    supabase.from("clinic_location").select("id, name").order("name"),
    // Nạp dịch vụ + bác sĩ khi vai INTAKE (đặt/đổi/hủy lịch) — cho cả modal đổi
    // lịch (canManage) lẫn nút "Đặt lịch" (canEdit gồm Lễ tân).
    canEdit
      ? supabase.from("service_type").select("id, name").order("name")
      : Promise.resolve({ data: [] as { id: string; name: string }[] }),
    canEdit ? listBookableDoctors() : Promise.resolve([]),
  ]);

  let { data, error } = patRes;
  // Thiếu cột full_name_unaccent (chưa migrate) → tìm lại không bỏ dấu.
  if (error && /full_name_unaccent|column/i.test(error.message ?? "")) {
    ({ data, error } = await buildPatientQuery(false));
  }

  const rows = (data as CustomerRow[] | null) ?? [];
  const locations: Opt[] = (locRes.data ?? []).map((r) => ({
    id: r.id as string,
    label: r.name as string,
  }));
  // Dropdown cho modal ĐỔI lịch — bỏ dịch vụ rác "FREE" (khớp trang đặt lịch).
  const services: Opt[] = ((svcRes.data ?? []) as { id: string; name: string }[])
    .filter((r) => (r.name ?? "").trim().toUpperCase() !== "FREE")
    .map((r) => ({ id: r.id, label: r.name }));
  const doctors: Opt[] = docRes;

  const shownIds = rows.map((r) => r.clinic_patient_id);
  // canManage: nạp thêm field để ĐIỀN SẴN modal đổi lịch (id/dịch vụ/bác sĩ/
  // cơ sở/kênh). Vai khác chỉ cần tóm tắt (nhẹ hơn).
  const apptSelectAll = canManage
    ? `clinic_patient_id, id, slot_start, status, service_type_id, doctor_id, location_id, booking_channel,
       service:service_type!service_type_id ( name ),
       doctor:staff!doctor_id ( full_name )`
    : "clinic_patient_id, slot_start, status";
  const apptsPromise = shownIds.length
    ? supabase
        .from("appointment")
        .select(apptSelectAll)
        .in("clinic_patient_id", shownIds)
        .order("slot_start", { ascending: true })
        .limit(3000)
    : Promise.resolve({ data: [] as unknown[] });
  // SỔ TƯƠNG TÁC — nguồn thật của cột "Tương tác gần nhất".
  //
  // `cskh_action` bên dưới là hàng nhập khẩu từ Notion và có 0 dòng trên bản
  // thật; hai câu INSERT duy nhất ghi vào nó còn không có cột `step` lẫn
  // `deadline_at`. Bảng mới ghi từ chính màn này (20260809000003).
  const tuongTacPromise = shownIds.length
    ? supabase
        .from("tuong_tac_cskh")
        .select(
          "clinic_patient_id, xay_ra_luc, loai, kenh, ket_qua, khach_xac_nhan, noi_dung, staff(full_name)",
        )
        .in("clinic_patient_id", shownIds)
        .order("xay_ra_luc", { ascending: false })
        .limit(1000)
    : Promise.resolve({ data: [] as unknown[], error: null });
  const cskhPromise = shownIds.length
    ? supabase
        .from("cskh_action")
        .select(
          "id, clinic_patient_id, category, step, status, description, deadline_at, source_created_at, created_by_text, last_edited_by_text",
        )
        .in("clinic_patient_id", shownIds)
        .order("source_created_at", { ascending: false })
        .limit(1000)
    : Promise.resolve({ data: [] as unknown[], error: null });

  // Lịch hẹn của các khách đang hiển thị → "lịch đại diện": SẮP TỚI gần nhất,
  // nếu không có thì lịch GẦN NHẤT trong quá khứ. Kèm tổng số lịch.
  const apptByPatient: Record<string, ApptInfo> = {};
  if (rows.length) {
    // Bắn CÙNG LÚC với truy vấn cskh_action bên dưới: cả hai chỉ cần `ids`, và
    // xếp hàng chúng là cộng thêm một lượt ~180ms sang Seoul mà không đổi kết
    // quả. `await` ở đây chỉ chờ đúng cái đã bay từ trước.
    const { data: appts } = await apptsPromise;
    const nowUtc = new Date().toISOString();
    type Raw = {
      clinic_patient_id: string;
      slot_start: string;
      status: string;
      id?: string;
      service_type_id?: string | null;
      doctor_id?: string | null;
      location_id?: string | null;
      booking_channel?: string | null;
      service?: { name: string } | { name: string }[] | null;
      doctor?: { full_name: string } | { full_name: string }[] | null;
    };
    const grouped: Record<string, Raw[]> = {};
    for (const a of (appts as unknown as Raw[] | null) ?? []) {
      (grouped[a.clinic_patient_id] ??= []).push(a);
    }
    const DEAD = ["CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"];
    for (const [pid, list] of Object.entries(grouped)) {
      // Lịch "sống" (bỏ đã hủy/không đến/BS từ chối) để chọn LỊCH ĐẠI DIỆN + đếm:
      // hủy lịch xong thì KHÔNG còn hiện là "Lịch hẹn sắp tới".
      const live = list.filter((a) => !DEAD.includes(a.status));
      const upcoming = live.find((a) => a.slot_start >= nowUtc); // sort tăng dần
      const repr = upcoming ?? live[live.length - 1];
      if (!repr) continue; // chỉ còn lịch đã hủy → coi như chưa có lịch hẹn
      // Chỉ cho ĐỔI/HỦY lịch còn "sống" & SẮP TỚI (repr là lịch upcoming).
      let appt: EditableAppt | undefined;
      const EDITABLE = ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"];
      if (canManage && upcoming && repr.id && EDITABLE.includes(repr.status)) {
        appt = {
          id: repr.id,
          slot_start: repr.slot_start,
          service_type_id: repr.service_type_id ?? null,
          service_name: pick1(repr.service)?.name ?? null,
          doctor_id: repr.doctor_id ?? null,
          doctor_name: pick1(repr.doctor)?.full_name ?? null,
          location_id: repr.location_id ?? null,
          booking_channel: repr.booking_channel ?? null,
        };
      }
      apptByPatient[pid] = {
        slot_start: repr.slot_start,
        status: repr.status,
        upcoming: Boolean(upcoming),
        count: live.length,
        // "Đã khám" = có ≥1 lịch COMPLETED (cùng định nghĩa "bệnh nhân" ở
        // /patient-list). Đang khám (CHECKED_IN/IN_PROGRESS) hay mới đặt/check-in
        // thì CHƯA tính — nút "Hồ sơ & lịch sử khám" sẽ ẩn.
        examined: list.some((a) => a.status === "COMPLETED"),
        appt,
      };
    }
  }

  // Lịch hẹn + CSKH actions (trạng thái, tương tác, hạn xử lý, phụ trách)
  type CskhRaw = {
    id: string;
    clinic_patient_id: string;
    category: string | null;
    step: string | null;
    status: string | null;
    description: string | null;
    deadline_at: string | null;
    source_created_at: string | null;
    created_by_text: string | null;
    last_edited_by_text: string | null;
  };
  const cskhByPatient: Record<
    string,
    {
      status: string;
      lastInteraction: string | null;
      nextStep: string | null;
      deadline: string | null;
      assignee: string | null;
    }
  > = {};
  let cskhError: { message: string } | null = null;

  if (rows.length) {
    // ĐỌC CẢ `error`. Bản trước chỉ lấy `data`, nên khi RLS chặn (nhân viên
    // chưa nối clinic_membership) truy vấn trả 0 dòng và bốn cột giữa hiện "—"
    // y hệt lúc chưa có dữ liệu. Không phân biệt được "chưa có việc nào" với
    // "anh không có quyền đọc" là kiểu hỏng tệ nhất: không ai đi tìm.
    const { data: cskhActions, error } = await cskhPromise;
    cskhError = error;

    // Group by patient, pick latest action
    const grouped: Record<string, CskhRaw[]> = {};
    for (const a of (cskhActions as CskhRaw[] | null) ?? []) {
      if (a.clinic_patient_id) {
        (grouped[a.clinic_patient_id] ??= []).push(a);
      }
    }
    for (const [pid, actionList] of Object.entries(grouped)) {
      const latest = actionList[0]; // already sorted DESC
      if (!latest) continue;
      cskhByPatient[pid] = {
        status: latest.status ?? "OPEN",
        lastInteraction: latest.description ?? null,
        nextStep: latest.step ?? null,
        deadline: latest.deadline_at ?? null,
        assignee:
          latest.last_edited_by_text ?? latest.created_by_text ?? null,
      };
    }
  }

  // Gom sổ tương tác theo khách. Dòng đầu mỗi nhóm là lần gần nhất (đã sắp xếp
  // giảm dần ở truy vấn).
  type TuongTacRaw = {
    clinic_patient_id: string;
    xay_ra_luc: string;
    loai: string;
    kenh: string;
    ket_qua: string | null;
    khach_xac_nhan: boolean | null;
    noi_dung: string | null;
    staff?: { full_name: string } | { full_name: string }[] | null;
  };
  const tuongTacByPatient: Record<string, DongLichSu[]> = {};
  let tuongTacError: { message: string } | null = null;
  if (rows.length) {
    const { data: tt, error: ttErr } = await tuongTacPromise;
    tuongTacError = ttErr;
    for (const t of (tt as TuongTacRaw[] | null) ?? []) {
      const nv = Array.isArray(t.staff) ? t.staff[0] : t.staff;
      (tuongTacByPatient[t.clinic_patient_id] ??= []).push({
        xay_ra_luc: t.xay_ra_luc,
        loai: t.loai,
        kenh: t.kenh,
        ket_qua: t.ket_qua,
        khach_xac_nhan: t.khach_xac_nhan,
        noi_dung: t.noi_dung,
        nhan_vien: nv?.full_name ?? null,
        nguon: "tuong_tac",
      });
    }
  }

  return (
    <div className="space-y-3">
      {/* Tiêu đề nằm ở THANH TRÊN CÙNG (GlobalHeader) — nó đã hiện đúng
          "Quản lý khách hàng" kèm chính câu mô tả này. */}

      {error || cskhError || tuongTacError ? (
        <div className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
          {(error ?? cskhError ?? tuongTacError)?.message}
        </div>
      ) : (
        <CustomersView
          rows={rows}
          apptByPatient={apptByPatient}
          cskhByPatient={cskhByPatient}
          tuongTacByPatient={tuongTacByPatient}
          locations={locations}
          q={q}
          period={period}
          by={by}
          initialSelected={selected}
          canEdit={canEdit}
          canManage={canManage}
          services={services}
          doctors={doctors}
        />
      )}
    </div>
  );
}
