"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  Filter,
  Search,
  UserRoundPlus,
  UsersRound,
  X,
} from "lucide-react";
import { useMemo, useState, useTransition,
  useCallback,
} from "react";

import StatCard, { StatRow } from "@/components/ui/StatCard";
import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
import { fmtDate, fmtDateTimeOrDate } from "@/lib/datetime";
import { unaccentVi } from "@/lib/validation";
import PatientAdminEditor from "../PatientAdminEditor";
import QuickBookingModal from "../patient-list/QuickBookingModal";
import BaoXepBacSi from "./BaoXepBacSi";
import GhiTuongTac, { type DongLichSu } from "./GhiTuongTac";

/** Một dòng của view `v_trang_thai_cskh` — việc gấp nhất đang mở của một khách. */
export interface TrangThaiCskh {
  clinic_patient_id: string;
  trang_thai: string;
  /** Nhãn hiển thị, lấy từ bảng `luat_cskh` — phòng khám đổi chữ được. */
  nhan: string;
  han_xu_ly: string | null;
  qua_han: boolean;
  appointment_id: string | null;
  da_xac_nhan: boolean;
}

// Màu theo mức gấp, KHÔNG theo thứ tự bảng chữ cái. Đỏ dành cho việc mà chậm
// một ngày là khách đi về tay không.
const TONE_VIEC: Record<string, StatusTone> = {
  CHO_BAC_SI: "in_progress",
  KQ_CHUA_GUI: "assigned",
  CHO_KQ_XN: "ready",
  GOI_LAI: "assigned",
  HOI_LY_DO_HUY: "ready",
  HEN_GOI_LAI: "ready",
  NHAC_DI_KHAM: "assigned",
  NHAC_HEN_MAI: "assigned",
  MOI_TAI_KHAM: "ready",
  CHO_XAC_NHAN: "ready",
};

// Việc phải làm, viết ở thể mệnh lệnh. Nhãn trạng thái nói KHÁCH đang ở đâu;
// cột này nói NGƯỜI TRỰC phải nhấc máy lên làm gì.
const BUOC_TIEP: Record<string, string> = {
  CHO_BAC_SI: "Nhắc bác sĩ duyệt kết quả",
  KQ_CHUA_GUI: "Gọi trả kết quả cho khách",
  CHO_KQ_XN: "Hỏi đơn vị xét nghiệm",
  GOI_LAI: "Gọi lại (lần trước chưa gặp)",
  HOI_LY_DO_HUY: "Gọi hỏi vì sao huỷ",
  HEN_GOI_LAI: "Đã hẹn gọi lại hôm nay",
  NHAC_DI_KHAM: "Gọi nhắc đi khám",
  NHAC_HEN_MAI: "Gọi nhắc hẹn ngày mai",
  MOI_TAI_KHAM: "Gọi mời tái khám",
  CHO_XAC_NHAN: "Gọi xác nhận lịch",
};

const NHAN_LOAI_NGAN: Record<string, string> = {
  XAC_NHAN_LICH: "Xác nhận lịch",
  NHAC_HEN: "Nhắc hẹn",
  CHECK_XN: "Hỏi đơn vị XN",
  TRA_KQ: "Trả kết quả",
  HOI_LY_DO_HUY: "Hỏi lý do huỷ",
  HOI_THAM: "Hỏi thăm",
  KHAC: "Việc khác",
};
const NHAN_KQ_NGAN: Record<string, string> = {
  DA_LIEN_HE: "đã liên hệ",
  CHUA_NGHE_MAY: "không nghe máy",
  KHONG_LIEN_LAC_DUOC: "không liên lạc được",
  HEN_GOI_LAI: "khách hẹn gọi lại",
  CAN_BAC_SI: "cần hỏi bác sĩ",
  TU_CHOI: "từ chối",
  BO_QUA: "bỏ qua",
};

/** Một dòng cho ô "Tương tác gần nhất". `undefined` = chưa có lần nào. */
function tomTatTuongTac(ds: DongLichSu[] | undefined): string | undefined {
  const d = ds?.[0];
  if (!d) return undefined;
  const ngay = new Date(d.xay_ra_luc).toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
  const kq = d.ket_qua ? ` · ${NHAN_KQ_NGAN[d.ket_qua] ?? d.ket_qua}` : "";
  return `${ngay} · ${NHAN_LOAI_NGAN[d.loai] ?? d.loai}${kq}`;
}
import AppointmentEditModal, { type EditableAppt } from "./AppointmentEditModal";

export interface CustomerRow {
  clinic_patient_id: string;
  patient_code: string;
  full_name: string;
  date_of_birth: string | null;
  birth_year: number | null;
  phone_primary: string | null;
  phone_secondary: string | null;
  gender: string | null;
  ethnicity: string | null;
  nationality: string | null;
  occupation: string | null;
  patient_objection: string | null;
  address: string | null;
  guardian_name: string | null;
  location_id: string | null;
  created_at: string | null;
  van_de_di_kham: string | null;
  linh_vuc: string | null;
}

export interface ApptInfo {
  slot_start: string;
  status: string;
  upcoming: boolean;
  count: number;
  examined: boolean;
  appt?: EditableAppt;
}

export interface Opt {
  id: string;
  label: string;
}

export type Period = "today" | "week" | "month" | "all";
export type ByDim = "created" | "appt";

type CustomerTab =
  | "all"
  | "upcoming"
  | "examined"
  | "qua_sla"
  | "cho_xac_nhan";

const PERIODS: { key: Period; label: string }[] = [
  { key: "today", label: "Hôm nay" },
  { key: "week", label: "Tuần này" },
  { key: "month", label: "Tháng này" },
  { key: "all", label: "Tất cả" },
];

// LỌC BẰNG CHÍNH BỐN Ô SỐ Ở TRÊN — không có hàng tab riêng nữa.
//
// Trước đây màn này có cả hai, và bốn nhãn tab KHÔNG khớp bốn con số: tab ghi
// "Quá SLA" nhưng lọc `without_appointment` (khách chưa có lịch hẹn), tab
// "Nhiệm vụ hôm nay" lại lọc `examined`. Bấm vào một tab rồi so với con số ở
// trên là ra hai kết quả khác nhau, và không có gì trên màn hình nói vì sao.
//
// Nay mỗi ô số VÀ phép lọc của nó dùng CHUNG một vị từ (`hopVoiTab`), nên bấm ô
// đang hiện 29 thì thấy đúng 29 dòng ấy. Không còn tab "Tất cả khách hàng":
// mặc định đã là tất cả, và bỏ lọc bằng cách bấm lại ô đang chọn.

function initials(name: string): string {
  return (
    name
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(-2)
      .map((word) => word[0]?.toLocaleUpperCase("vi-VN") ?? "")
      .join("") || "KH"
  );
}

function appointmentStatus(status: string): { label: string; tone: StatusTone } {
  const known: Record<string, { label: string; tone: StatusTone }> = {
    SCHEDULED: { label: "Chờ xác nhận (lịch cũ)", tone: "ready" },
    CSKH_CONFIRMED: { label: "Chờ bác sĩ (lịch cũ)", tone: "assigned" },
    CONFIRMED: { label: "Đã đặt lịch", tone: "assigned" },
    CHECKED_IN: { label: "Đã check-in", tone: "in_progress" },
    COMPLETED: { label: "Đã khám xong", tone: "completed" },
    CANCELLED: { label: "Đã hủy", tone: "cancelled" },
    NO_SHOW: { label: "Không đến", tone: "cancelled" },
    DOCTOR_DECLINED: { label: "Bác sĩ từ chối", tone: "cancelled" },
  };
  return known[status] ?? { label: status, tone: "ready" };
}

function CustomerTableHeader() {
  return (
    <div className="grid grid-cols-[minmax(180px,1.2fr)_minmax(100px,0.7fr)_minmax(180px,1.2fr)_minmax(180px,1.2fr)_minmax(100px,0.7fr)_minmax(90px,0.6fr)_32px] gap-3 border-b border-line bg-surface-muted px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
      <span>Khách hàng</span>
      <span>Trạng thái</span>
      <span>Tương tác gần nhất</span>
      <span>Bước tiếp theo</span>
      <span>Hạn xử lý</span>
      <span>Phụ trách</span>
      <span aria-hidden="true" />
    </div>
  );
}

export default function CustomersView({
  rows,
  apptByPatient,
  cskhByPatient,
  tuongTacByPatient,
  trangThaiByPatient,
  locations,
  q,
  period,
  by,
  initialSelected,
  canEdit = false,
  canManage = false,
  services = [],
  doctors = [],
}: {
  rows: CustomerRow[];
  apptByPatient: Record<string, ApptInfo>;
  cskhByPatient: Record<
    string,
    {
      status: string;
      lastInteraction: string | null;
      nextStep: string | null;
      deadline: string | null;
      assignee: string | null;
    }
  >;
  tuongTacByPatient: Record<string, DongLichSu[]>;
  trangThaiByPatient: Record<string, TrangThaiCskh>;
  locations: Opt[];
  q: string;
  period: Period;
  by: ByDim;
  initialSelected: string | null;
  canEdit?: boolean;
  canManage?: boolean;
  services?: Opt[];
  doctors?: Opt[];
}) {
  const router = useRouter();
  const [tab, setTab] = useState<CustomerTab>("all");
  
  /** Bấm một ô số = lọc theo ô đó. Bấm lại đúng ô đang chọn = bỏ lọc. */
  const chonLoc = (key: CustomerTab) =>
    setTab((cu) => (cu === key ? "all" : key));
  const [selectedId, setSelectedId] = useState<string | null>(initialSelected);
  const [term, setTerm] = useState(q);
  const [editOpen, setEditOpen] = useState(false);
  const [bookOpen, setBookOpen] = useState(false);
  // actionLoading/actionMsg đi cùng hai nút "xác nhận khách sẽ tới" / "báo
  // không tới" đã bỏ — xem ghi chú ở khối nút bên dưới.
  const [isPending, startTransition] = useTransition();

  function go(nextPeriod: Period, nextQ: string, nextBy: ByDim) {
    const params = new URLSearchParams();
    if (nextQ.trim()) params.set("q", nextQ.trim());
    if (nextPeriod !== "all") params.set("period", nextPeriod);
    if (nextBy !== "created") params.set("by", nextBy);
    if (selectedId) params.set("selected", selectedId);
    const query = params.toString();
    startTransition(() => {
      router.push(`/customers${query ? `?${query}` : ""}`);
    });
  }

  const locName = (id: string | null) =>
    locations?.find((location) => location.id === id)?.label ?? "—";

  const searchedRows = useMemo(() => {
    const needle = unaccentVi(term.trim());
    if (!needle) return rows;
    return rows.filter((row) => {
      return [row.full_name, row.patient_code, row.phone_primary ?? ""]
        .map(unaccentVi)
        .some((value) => value.includes(needle));
    });
  }, [rows, term]);

  /** MỘT vị từ cho cả việc đếm ô số lẫn việc lọc danh sách.
   *
   * Đây là chỗ bản cũ sai: con số trên ô và phép lọc của tab được tính bằng hai
   * đoạn mã khác nhau, nên chúng nói hai điều khác nhau về cùng một tập khách.
   */
  const hopVoiTab = useCallback(
    (row: CustomerRow, key: CustomerTab): boolean => {
      if (key === "all") return true;
      const appointment = apptByPatient[row.clinic_patient_id];
      if (key === "upcoming") return Boolean(appointment?.upcoming) || !appointment;
      if (key === "examined") return Boolean(appointment?.examined);
      if (key === "qua_sla") {
        const dl = cskhByPatient[row.clinic_patient_id]?.deadline;
        return Boolean(dl && new Date(dl) < new Date());
      }
      if (key === "cho_xac_nhan") return appointment?.status === "SCHEDULED";
      return true;
    },
    [apptByPatient, cskhByPatient],
  );

  const visibleRows = useMemo(
    () => searchedRows.filter((row) => hopVoiTab(row, tab)),
    [searchedRows, tab, hopVoiTab],
  );

  const selected =
    selectedId === null
      ? null
      : (visibleRows.find((row) => row.clinic_patient_id === selectedId) ?? null);

  const selectedAppt = selected
    ? apptByPatient[selected.clinic_patient_id]
    : undefined;

  // Ba biến đếm cũ đã BỎ. Chúng tính bằng một đoạn mã riêng, tách khỏi phép
  // lọc của tab — và đó chính là chỗ con số trên ô và danh sách bên dưới nói
  // hai điều khác nhau. Nay cả hai đi qua `hopVoiTab`.

  // TRẠNG THÁI = VIỆC ĐANG MỞ, không phải "khách này đang ở đâu".
  //
  // View `v_trang_thai_cskh` trả về việc gấp nhất và nhãn của nó (nhãn lấy từ
  // bảng luat_cskh, nên phòng khám đổi chữ mà không cần deploy). Không có việc
  // nào thì nói thẳng "Không có việc" — thay cho "Đã đặt lịch", câu mà màn cũ
  // hiện cho gần như mọi khách và không nói CSKH phải làm gì tiếp.
  //
  // Hai nguồn cũ giữ lại làm đường lùi cho tới khi cskh_action được chốt thành
  // dữ liệu nhập khẩu chỉ đọc.
  function customerStatus(row: CustomerRow): { label: string; tone: StatusTone } {
    const tt = trangThaiByPatient[row.clinic_patient_id];
    if (tt) {
      return { label: tt.nhan, tone: tt.qua_han ? "overdue" : TONE_VIEC[tt.trang_thai] ?? "ready" };
    }
    const cskh = cskhByPatient[row.clinic_patient_id];
    const appt = apptByPatient[row.clinic_patient_id];
    if (cskh) {
      const statusMap: Record<string, { label: string; tone: StatusTone }> = {
        DONE: { label: "Hoàn thành", tone: "completed" },
        CLOSED: { label: "Hoàn thành", tone: "completed" },
        WAITING: { label: "Chờ phản hồi", tone: "ready" },
        IN_PROGRESS: { label: "Đang tư vấn", tone: "assigned" },
        OPEN: { label: "Đang xử lý", tone: "in_progress" },
      };
      return statusMap[cskh.status] ?? { label: cskh.status, tone: "ready" };
    }
    if (appt) {
      return appointmentStatus(appt.status);
    }
    return { label: "Khách mới", tone: "ready" };
  }

  /** Việc phải làm tiếp — chính là tên của trạng thái, viết ở thể mệnh lệnh. */
  function customerNextStep(row: CustomerRow): string | undefined {
    const tt = trangThaiByPatient[row.clinic_patient_id];
    return tt ? (BUOC_TIEP[tt.trang_thai] ?? tt.nhan) : undefined;
  }

  function customerDeadline(row: CustomerRow): { text: string; overdue: boolean } {
    const tt = trangThaiByPatient[row.clinic_patient_id];
    if (tt?.han_xu_ly) {
      // View đã tính `qua_han` theo giờ Việt Nam. Tính lại ở trình duyệt là
      // mời máy của người dùng — múi giờ nào cũng có — vào quyết định một câu
      // hỏi nghiệp vụ.
      return { text: fmtDate(tt.han_xu_ly), overdue: tt.qua_han };
    }
    const cskh = cskhByPatient[row.clinic_patient_id];
    if (!cskh?.deadline) return { text: "—", overdue: false };
    const now = new Date();
    const dl = new Date(cskh.deadline);
    const diffMin = Math.floor((dl.getTime() - now.getTime()) / 60000);
    if (diffMin < 0) {
      const overMin = -diffMin;
      if (overMin < 60) return { text: `Quá hạn ${overMin} phút`, overdue: true };
      const overHours = Math.floor(overMin / 60);
      if (overHours < 24) return { text: `Quá hạn ${overHours} giờ`, overdue: true };
      return { text: `Quá hạn ${Math.floor(overHours / 24)} ngày`, overdue: true };
    }
    if (diffMin < 60) return { text: `Còn ${diffMin} phút`, overdue: false };
    const hours = Math.floor(diffMin / 60);
    if (hours < 24) return { text: fmtDateTimeOrDate(cskh.deadline), overdue: false };
    return { text: fmtDate(cskh.deadline), overdue: false };
  }

  return (
    <div className="space-y-4">
      <StatRow>
        <StatCard
          label="Cần xử lý hôm nay"
          value={rows.filter((r) => hopVoiTab(r, "upcoming")).length}
          tone="brand"
          icon={<UsersRound className="size-5" />}
          onSelect={() => chonLoc("upcoming")}
          active={tab === "upcoming"}
        />
        <StatCard
          label="Quá SLA"
          value={rows.filter((r) => hopVoiTab(r, "qua_sla")).length}
          tone="danger"
          icon={<CalendarClock className="size-5 text-danger" />}
          onSelect={() => chonLoc("qua_sla")}
          active={tab === "qua_sla"}
        />
        <StatCard
          label="Chờ xác nhận"
          value={rows.filter((r) => hopVoiTab(r, "cho_xac_nhan")).length}
          tone="warning"
          icon={<CalendarClock className="size-5 text-warning" />}
          onSelect={() => chonLoc("cho_xac_nhan")}
          active={tab === "cho_xac_nhan"}
        />
        <StatCard
          label="Đã hoàn thành"
          value={rows.filter((r) => hopVoiTab(r, "examined")).length}
          tone="success"
          icon={<CheckCircle2 className="size-5 text-success" />}
          onSelect={() => chonLoc("examined")}
          active={tab === "examined"}
        />
      </StatRow>

      {tab !== "all" ? (
        <div className="flex items-center gap-2 text-sm text-ink-muted">
          <span>Đang lọc theo ô số đã chọn</span>
          <button
            type="button"
            onClick={() => setTab("all")}
            className="rounded-control px-2 py-0.5 font-medium text-brand-700 underline-offset-2 hover:underline"
          >
            Bỏ lọc, xem tất cả khách hàng
          </button>
        </div>
      ) : null}

      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line">
        {canEdit ? (
          <Link
            href="/patients/new"
            className="mb-2 inline-flex min-h-10 items-center gap-2 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 shadow-xs transition-all"
          >
            <UserRoundPlus className="size-4" aria-hidden="true" />
            Thêm khách hàng
          </Link>
        ) : null}
      </div>

      <div className="flex flex-col gap-2 rounded-2xl border border-line bg-surface p-3 shadow-card lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
          <label className="flex min-h-10 min-w-[240px] flex-1 items-center gap-2 rounded-xl border border-line bg-surface px-3 text-ink-muted focus-within:border-brand-500 lg:max-w-md">
            <Search className="size-4" aria-hidden="true" />
            <input
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="Tìm theo tên, số điện thoại, mã khách hàng"
              className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
            />
          </label>
          <label className="flex min-h-10 items-center gap-2 rounded-xl border border-line px-3 text-sm text-ink-soft bg-surface">
            <Filter className="size-4" aria-hidden="true" />
            <select
              value={by}
              onChange={(event) => go(period, term, event.target.value as ByDim)}
              aria-label="Bộ lọc"
              className="bg-transparent outline-none"
            >
              <option value="created">Bộ lọc</option>
              <option value="appt">Ngày hẹn</option>
            </select>
          </label>
        </div>
        <div className="flex flex-wrap gap-1 rounded-xl bg-surface-sunken p-1" role="group">
          {PERIODS.map((entry) => (
            <button
              key={entry.key}
              type="button"
              onClick={() => go(entry.key, term, by)}
              className={`rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all ${
                entry.key === period
                  ? "bg-surface text-ink shadow-card font-bold"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              {entry.label}
            </button>
          ))}
        </div>
      </div>

      <div className={`grid items-start gap-3 ${selected ? "xl:grid-cols-[minmax(0,1fr)_minmax(320px,380px)]" : "grid-cols-1"}`}>
        <section
          aria-label="Danh sách khách hàng"
          className="min-w-0 overflow-hidden rounded-2xl border border-line bg-surface shadow-card"
        >
          <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-ink">Danh sách khách hàng</h2>
              <p className="mt-0.5 text-xs text-ink-muted">
                {visibleRows.length} khách hàng {isPending ? " · đang tìm…" : ""}
              </p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <div className="min-w-[960px]">
              <CustomerTableHeader />
              {visibleRows.length > 0 ? (
                <div className="divide-y divide-line">
                  {visibleRows.map((row) => {
                    const active = selected?.clinic_patient_id === row.clinic_patient_id;
                    const cskh = cskhByPatient[row.clinic_patient_id];
                    const st = customerStatus(row);
                    const dl = customerDeadline(row);

                    return (
                      <div
                        key={row.clinic_patient_id}
                        onClick={() => setSelectedId(row.clinic_patient_id)}
                        className={`grid w-full grid-cols-[minmax(180px,1.2fr)_minmax(100px,0.7fr)_minmax(180px,1.2fr)_minmax(180px,1.2fr)_minmax(100px,0.7fr)_minmax(90px,0.6fr)_32px] items-center gap-3 px-4 py-3 text-left transition-colors cursor-pointer ${
                          active ? "bg-brand-50/60" : "hover:bg-surface-sunken"
                        }`}
                      >
                        <div className="min-w-0">
                          <span className="block truncate text-sm font-bold text-ink">
                            {row.full_name}
                          </span>
                          <span className="mt-0.5 block truncate font-mono text-xs text-ink-muted">
                            {row.patient_code}
                          </span>
                        </div>
                        <div>
                          <StatusChip tone={st.tone} label={st.label} />
                        </div>
                        <div className="min-w-0 text-xs text-ink-soft truncate">
                          {tomTatTuongTac(tuongTacByPatient[row.clinic_patient_id]) ??
                      cskh?.lastInteraction ??
                      "—"}
                        </div>
                        <div className="min-w-0">
                          <span className="truncate text-xs font-medium text-ink">
                            {customerNextStep(row) ?? cskh?.nextStep ?? "—"}
                          </span>
                        </div>
                        <div>
                          <span
                            className={`text-xs font-semibold ${
                              dl.overdue
                                ? "rounded-md bg-danger-bg px-2 py-0.5 text-danger font-bold"
                                : "text-ink-muted"
                            }`}
                          >
                            {dl.text}
                          </span>
                        </div>
                        <div className="text-xs font-medium text-ink truncate">
                          {cskh?.assignee ?? "—"}
                        </div>
                        <div className="text-right">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedId(row.clinic_patient_id);
                            }}
                            className="rounded-lg p-1 text-ink-muted hover:bg-surface-sunken hover:text-ink"
                          >
                            ⋮
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="px-4 py-14 text-center text-sm text-ink-muted">
                  {term.trim()
                    ? "Không tìm thấy khách khớp từ khoá."
                    : "Không có khách hàng trong khoảng lọc này."}
                </p>
              )}
            </div>
          </div>
        </section>

        {selected && (
          <aside
            aria-label="Chi tiết khách hàng"
            className="min-h-[420px] rounded-2xl border border-line bg-surface p-4 shadow-card xl:max-h-[720px] xl:overflow-y-auto animate-in fade-in duration-150"
          >
          {selected ? (
            <>
              <div className="flex items-start gap-3 border-b border-line pb-4">
                <span className="grid size-11 shrink-0 place-items-center rounded-full bg-surface-sunken text-sm font-semibold text-ink-soft">
                  {initials(selected.full_name)}
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-base font-semibold text-ink">{selected.full_name}</h2>
                  <p className="mt-0.5 font-mono text-xs text-ink-muted">{selected.patient_code}</p>
                  <p className="mt-1 text-sm text-ink-muted">
                    {selected.phone_primary ?? "Chưa có số điện thoại"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedId(null)}
                  aria-label="Đóng chi tiết khách hàng"
                  className="rounded-control p-1.5 text-ink-muted hover:bg-surface-sunken hover:text-ink"
                >
                  <X className="size-4" aria-hidden="true" />
                </button>
              </div>

              <div className="space-y-3 py-4">
                {canManage && selectedAppt?.appt ? (
                  <button
                    type="button"
                    onClick={() => setEditOpen(true)}
                    className="flex w-full items-start gap-2 rounded-control border border-line bg-surface-muted p-3 text-left hover:border-brand-500"
                  >
                    <CalendarClock className="mt-0.5 size-4 shrink-0 text-brand-700" aria-hidden="true" />
                    <span>
                      <span className="block text-xs text-ink-muted">Lịch hẹn sắp tới</span>
                      <span className="mt-1 block text-sm font-semibold text-ink">
                        {fmtDateTimeOrDate(selectedAppt.slot_start)}
                      </span>
                      <span className="mt-1 block text-xs text-brand-700">Bấm để đổi hoặc hủy lịch</span>
                    </span>
                  </button>
                ) : (
                  <div className="rounded-control border border-line bg-surface-muted p-3">
                    <p className="text-xs text-ink-muted">
                      {selectedAppt?.upcoming ? "Lịch hẹn sắp tới" : "Lịch hẹn"}
                    </p>
                    <p className="mt-1 text-sm font-semibold text-ink">
                      {selectedAppt
                        ? fmtDateTimeOrDate(selectedAppt.slot_start)
                        : "Chưa có lịch hẹn"}
                    </p>
                  </div>
                )}

                {/* CSKH & Lễ tân: Khung Xác nhận lịch hẹn & Gọi điện */}
                <div className="space-y-2 rounded-2xl border border-brand-200 bg-brand-50/50 p-3 text-xs shadow-xs">
                  <div className="flex items-center justify-between font-bold text-brand-800">
                    <span>XÁC NHẬN LỊCH HẸN &amp; TƯƠNG TÁC</span>
                    <span className="rounded-full bg-brand-200 px-2 py-0.5 text-[10px] text-brand-800 font-mono">
                      CSKH / Lễ tân
                    </span>
                  </div>

                  {/* GỌI XONG THÌ GHI LẠI.
                      Trước đây chỗ này là một thẻ `<a href="tel:">` và một nút
                      "Zalo/SMS" gắn cứng disabled. Quay số xong hệ thống không
                      biết gì, nên cột "Tương tác gần nhất" hiện "—" cho mọi
                      khách kể cả những người vừa được gọi sáng nay. */}
                  <div className="pt-1">
                    <GhiTuongTac
                      clinicPatientId={selected.clinic_patient_id}
                      appointmentId={selectedAppt?.appt?.id ?? null}
                      phone={selected.phone_primary}
                      lichSuBanDau={
                        tuongTacByPatient[selected.clinic_patient_id] ?? []
                      }
                    />
                  </div>

                  {/* KHÔNG CÒN NÚT "XÁC NHẬN KHÁCH SẼ TỚI".
                      Quang (2026-08-04): lịch hẹn sinh ra từ chính cuộc gọi
                      hoặc tin nhắn với bệnh nhân, nên nó đã chắc ngay lúc đặt
                      — gọi lại để xác nhận cái vừa thoả thuận là làm hai lần
                      một việc. Đổi hoặc huỷ thì bấm vào "Lịch hẹn sắp tới" ở
                      trên, và phải ghi lý do.

                      "Báo không tới" cũng bỏ khỏi đây: đánh vắng là việc của
                      Lễ tân TẠI THỜI ĐIỂM bệnh nhân không đến, không phải việc
                      CSKH đoán trước qua điện thoại. */}
                  <div className="space-y-1.5 pt-1">
                    {/* CHƯA CÓ BÁC SĨ → việc của CSKH là báo quản lý, không
                        phải tự chọn: họ không biết ai trực tuần đó. Nút chỉ
                        hiện khi lịch thật sự còn trống bác sĩ. */}
                    {selectedAppt?.appt && !selectedAppt.appt.doctor_id && (
                      <BaoXepBacSi appointmentId={selectedAppt.appt.id} />
                    )}
                    <button
                      type="button"
                      disabled={!canManage || !selectedAppt?.appt}
                      onClick={() => setEditOpen(true)}
                      className="w-full inline-flex items-center justify-center gap-1.5 rounded-xl border border-line bg-surface py-2 px-3 text-xs font-semibold text-ink-soft hover:bg-surface-muted disabled:opacity-50"
                    >
                      Đổi / huỷ lịch hẹn (ghi lý do)
                    </button>
                  </div>

                </div>

                {canEdit && !selectedAppt?.upcoming ? (
                  <button
                    type="button"
                    onClick={() => setBookOpen(true)}
                    className="flex min-h-10 w-full items-center justify-center gap-2 rounded-control bg-brand-600 px-3 text-sm font-semibold text-white hover:bg-brand-700"
                  >
                    <CalendarClock className="size-4" aria-hidden="true" />
                    Đặt lịch mới
                  </button>
                ) : null}

                {canEdit ? (
                  <>
                    <PatientAdminEditor
                      key={selected.clinic_patient_id}
                      patient={{
                        clinic_patient_id: selected.clinic_patient_id,
                        full_name: selected.full_name,
                        date_of_birth: selected.date_of_birth,
                        phone_primary: selected.phone_primary,
                        phone_secondary: selected.phone_secondary,
                        gender: selected.gender,
                        ethnicity: selected.ethnicity,
                        nationality: selected.nationality,
                        occupation: selected.occupation,
                        patient_objection: selected.patient_objection,
                        address: selected.address,
                        guardian_name: selected.guardian_name,
                        van_de_di_kham: selected.van_de_di_kham,
                        linh_vuc: selected.linh_vuc,
                      }}
                    />
                    <dl className="space-y-1.5 text-sm">
                      <DetailRow label="Cơ sở" value={locName(selected.location_id)} />
                      <DetailRow label="Ngày tạo" value={fmtDateTimeOrDate(selected.created_at)} />
                    </dl>
                  </>
                ) : (
                  <dl className="space-y-2 text-sm">
                    <DetailRow label="Ngày sinh" value={dobDisplay(selected)} />
                    <DetailRow label="Giới tính" value={selected.gender} />
                    <DetailRow label="SĐT chính" value={selected.phone_primary} />
                    <DetailRow label="SĐT người nhà" value={selected.phone_secondary} />
                    <DetailRow label="Dân tộc" value={selected.ethnicity} />
                    <DetailRow label="Quốc tịch" value={selected.nationality} />
                    <DetailRow label="Nghề nghiệp" value={selected.occupation} />
                    <DetailRow label="Đối tượng" value={selected.patient_objection} />
                    <DetailRow label="Địa chỉ" value={selected.address} />
                    <DetailRow label="Cơ sở" value={locName(selected.location_id)} />
                    <DetailRow label="Ngày tạo" value={fmtDateTimeOrDate(selected.created_at)} />
                  </dl>
                )}

                {selectedAppt?.examined ? (
                  <Link
                    href={`/patients/${selected.clinic_patient_id}`}
                    className="flex min-h-10 items-center justify-center gap-2 rounded-control border border-brand-500 bg-surface px-3 text-sm font-semibold text-brand-700 hover:bg-brand-50"
                  >
                    <ExternalLink className="size-4" aria-hidden="true" />
                    Hồ sơ và lịch sử khám
                  </Link>
                ) : null}
              </div>
            </>
          ) : (
            <div className="grid min-h-80 place-items-center text-center">
              <div>
                <UsersRound className="mx-auto size-7 text-ink-faint" aria-hidden="true" />
                <p className="mt-3 text-sm font-medium text-ink">Chọn một khách hàng</p>
                <p className="mt-1 text-xs text-ink-muted">
                  Thông tin hành chính và lịch hẹn sẽ hiện ở đây.
                </p>
              </div>
            </div>
          )}
        </aside>
        )}
      </div>

      {editOpen && selected && selectedAppt?.appt ? (
        <AppointmentEditModal
          appt={selectedAppt.appt}
          patientName={selected.full_name}
          clinicPatientId={selected.clinic_patient_id}
          services={services}
          doctors={doctors}
          locations={locations}
          onClose={() => setEditOpen(false)}
        />
      ) : null}

      {bookOpen && selected ? (
        <QuickBookingModal
          patient={{
            clinic_patient_id: selected.clinic_patient_id,
            full_name: selected.full_name,
            patient_code: selected.patient_code,
          }}
          services={services}
          doctors={doctors}
          locations={locations}
          onClose={() => setBookOpen(false)}
          onBooked={() => {
            setBookOpen(false);
            router.refresh();
          }}
        />
      ) : null}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-2">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="min-w-0 break-words text-ink">{value || "—"}</dd>
    </div>
  );
}

function dobDisplay(row: CustomerRow): string | null {
  if (row.birth_year) return `${row.birth_year} (chỉ năm)`;
  return row.date_of_birth ? fmtDate(row.date_of_birth) : null;
}
