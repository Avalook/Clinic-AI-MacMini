"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  CircleSlash2,
  ExternalLink,
  Filter,
  Search,
  UserRoundPlus,
  UsersRound,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";

import StatCard, { StatRow } from "@/components/ui/StatCard";
import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
import { fmtDate, fmtDateTimeOrDate } from "@/lib/datetime";
import { unaccentVi } from "@/lib/validation";
import PatientAdminEditor from "../PatientAdminEditor";
import QuickBookingModal from "../patient-list/QuickBookingModal";
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

type CustomerTab = "all" | "upcoming" | "examined" | "without_appointment";

const PERIODS: { key: Period; label: string }[] = [
  { key: "today", label: "Hôm nay" },
  { key: "week", label: "Tuần này" },
  { key: "month", label: "Tháng này" },
  { key: "all", label: "Tất cả" },
];

const CUSTOMER_TABS: { key: CustomerTab; label: string }[] = [
  { key: "all", label: "Tất cả khách hàng" },
  { key: "upcoming", label: "Có lịch sắp tới" },
  { key: "examined", label: "Đã khám" },
  { key: "without_appointment", label: "Chưa có lịch" },
];

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
    SCHEDULED: { label: "Chờ xác nhận", tone: "ready" },
    CSKH_CONFIRMED: { label: "CSKH đã xác nhận", tone: "assigned" },
    CONFIRMED: { label: "Đã xác nhận", tone: "assigned" },
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
    <div className="grid grid-cols-[minmax(180px,1.2fr)_minmax(150px,0.9fr)_minmax(150px,0.9fr)_minmax(100px,0.55fr)_20px] gap-3 border-b border-line bg-surface-muted px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
      <span>Khách hàng</span>
      <span>Lịch hẹn</span>
      <span>Trạng thái lịch</span>
      <span>Ngày tạo</span>
      <span aria-hidden="true" />
    </div>
  );
}

export default function CustomersView({
  rows,
  apptByPatient,
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
  const [selectedId, setSelectedId] = useState<string | null>(initialSelected);
  const [term, setTerm] = useState(q);
  const [editOpen, setEditOpen] = useState(false);
  const [bookOpen, setBookOpen] = useState(false);
  const [isPending, startTransition] = useTransition();

  const locName = (id: string | null) =>
    locations.find((location) => location.id === id)?.label ?? "—";

  function go(nextPeriod: Period, nextQ: string, nextBy: ByDim) {
    const params = new URLSearchParams();
    if (nextQ.trim()) params.set("q", nextQ.trim());
    if (nextPeriod !== "all") params.set("period", nextPeriod);
    if (nextBy !== "created") params.set("by", nextBy);
    const query = params.toString();
    router.push(`/customers${query ? `?${query}` : ""}`);
  }

  const searchedRows = useMemo(() => {
    const needle = unaccentVi(term.trim());
    if (!needle) return rows;
    return rows.filter((row) => {
      return [row.full_name, row.patient_code, row.phone_primary ?? ""]
        .map(unaccentVi)
        .some((value) => value.includes(needle));
    });
  }, [rows, term]);

  const visibleRows = useMemo(() => {
    return searchedRows.filter((row) => {
      const appointment = apptByPatient[row.clinic_patient_id];
      if (tab === "upcoming") return Boolean(appointment?.upcoming);
      if (tab === "examined") return Boolean(appointment?.examined);
      if (tab === "without_appointment") return !appointment;
      return true;
    });
  }, [apptByPatient, searchedRows, tab]);

  const selected =
    visibleRows.find((row) => row.clinic_patient_id === selectedId) ?? null;
  const selectedAppt = selected
    ? apptByPatient[selected.clinic_patient_id]
    : undefined;

  const firstRun = useRef(true);
  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }
    if (term.trim() === q.trim()) return;
    const timeoutId = window.setTimeout(() => {
      startTransition(() => go(period, term, by));
    }, 350);
    return () => window.clearTimeout(timeoutId);
    // go carries only router and the props captured by this screen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [term]);

  const upcomingCount = rows.filter((row) => apptByPatient[row.clinic_patient_id]?.upcoming).length;
  const examinedCount = rows.filter((row) => apptByPatient[row.clinic_patient_id]?.examined).length;
  const noAppointmentCount = rows.filter((row) => !apptByPatient[row.clinic_patient_id]).length;

  return (
    <div className="space-y-3">
      <StatRow>
        <StatCard
          label="Khách hiển thị"
          value={rows.length}
          tone="brand"
          icon={<UsersRound className="size-5" />}
        />
        <StatCard
          label="Có lịch sắp tới"
          value={upcomingCount}
          tone="warning"
          icon={<CalendarClock className="size-5" />}
        />
        <StatCard
          label="Đã khám"
          value={examinedCount}
          tone="success"
          icon={<CheckCircle2 className="size-5" />}
        />
        <StatCard
          label="Chưa có lịch"
          value={noAppointmentCount}
          tone="neutral"
          icon={<CircleSlash2 className="size-5" />}
        />
      </StatRow>

      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line">
        <div className="flex overflow-x-auto text-sm">
          {CUSTOMER_TABS.map((entry) => (
            <button
              key={entry.key}
              type="button"
              onClick={() => setTab(entry.key)}
              aria-pressed={tab === entry.key}
              className={`shrink-0 border-b-2 px-3 py-2.5 font-medium transition-colors ${
                tab === entry.key
                  ? "border-brand-600 text-brand-700"
                  : "border-transparent text-ink-muted hover:text-ink"
              }`}
            >
              {entry.label}
            </button>
          ))}
        </div>
        {canEdit ? (
          <Link
            href="/patients/new"
            className="mb-2 inline-flex min-h-10 items-center gap-2 rounded-control bg-brand-600 px-3 text-sm font-semibold text-white hover:bg-brand-700"
          >
            <UserRoundPlus className="size-4" aria-hidden="true" />
            Thêm khách hàng
          </Link>
        ) : null}
      </div>

      <div className="flex flex-col gap-2 rounded-card border border-line bg-surface p-3 shadow-card lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
          <label className="flex min-h-10 min-w-[220px] flex-1 items-center gap-2 rounded-control border border-line bg-surface px-3 text-ink-muted focus-within:border-brand-500 lg:max-w-md">
            <Search className="size-4" aria-hidden="true" />
            <span className="sr-only">Tìm theo tên, số điện thoại, mã khách hàng</span>
            <input
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="Tìm theo tên, số điện thoại, mã khách hàng"
              className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
            />
          </label>
          <label className="flex min-h-10 items-center gap-2 rounded-control border border-line px-3 text-sm text-ink-soft">
            <Filter className="size-4" aria-hidden="true" />
            <span className="sr-only">Hiển thị theo</span>
            <select
              value={by}
              onChange={(event) => go(period, term, event.target.value as ByDim)}
              aria-label="Hiển thị theo"
              className="bg-transparent outline-none"
            >
              <option value="created">Ngày tạo</option>
              <option value="appt">Ngày hẹn</option>
            </select>
          </label>
        </div>
        <div className="flex flex-wrap gap-1 rounded-control bg-surface-sunken p-1" role="group" aria-label="Khoảng thời gian">
          {PERIODS.map((entry) => (
            <button
              key={entry.key}
              type="button"
              onClick={() => go(entry.key, term, by)}
              className={`rounded-control px-2.5 py-1.5 text-xs font-medium ${
                entry.key === period
                  ? "bg-surface text-ink shadow-card"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              {entry.label}
            </button>
          ))}
        </div>
      </div>

      {by === "appt" && period !== "all" ? (
        <p className="text-xs text-ink-muted">
          Đang xem khách có lịch hẹn trong khoảng thời gian đã chọn.
        </p>
      ) : null}

      <div className="grid items-start gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(300px,380px)]">
        <section
          aria-label="Danh sách khách hàng"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-3">
            <div>
              <h2 className="text-sm font-semibold text-ink">Danh sách khách hàng</h2>
              <p className="mt-0.5 text-xs text-ink-muted">
                {visibleRows.length} khách hàng
                {isPending ? " · đang tìm…" : ""}
                {rows.length >= 300 ? " · 300 khách gần nhất" : ""}
              </p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <div className="min-w-[720px]">
              <CustomerTableHeader />
              {visibleRows.length > 0 ? (
                <div className="divide-y divide-line">
                  {visibleRows.map((row) => {
                    const appointment = apptByPatient[row.clinic_patient_id];
                    const status = appointment ? appointmentStatus(appointment.status) : null;
                    const active = selected?.clinic_patient_id === row.clinic_patient_id;
                    return (
                      <button
                        key={row.clinic_patient_id}
                        type="button"
                        onClick={() => setSelectedId(row.clinic_patient_id)}
                        aria-current={active ? "true" : undefined}
                        className={`grid w-full grid-cols-[minmax(180px,1.2fr)_minmax(150px,0.9fr)_minmax(150px,0.9fr)_minmax(100px,0.55fr)_20px] items-center gap-3 px-3 py-3 text-left transition-colors ${
                          active ? "bg-surface-selected" : "hover:bg-surface-sunken"
                        }`}
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-semibold text-ink">
                            {row.full_name}
                          </span>
                          <span className="mt-0.5 block truncate font-mono text-xs text-ink-muted">
                            {row.patient_code}
                            {row.phone_primary ? ` · ${row.phone_primary}` : ""}
                          </span>
                        </span>
                        <span className="min-w-0 truncate text-sm text-ink-soft">
                          {appointment
                            ? `${appointment.upcoming ? "Sắp tới" : "Gần nhất"}: ${fmtDateTimeOrDate(appointment.slot_start)}`
                            : "Chưa có lịch"}
                        </span>
                        <span>{status ? <StatusChip tone={status.tone} label={status.label} /> : "—"}</span>
                        <span className="text-sm text-ink-muted">
                          {fmtDate(row.created_at)}
                        </span>
                        <ChevronRight className="size-4 text-ink-faint" aria-hidden="true" />
                      </button>
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

        <aside
          aria-label="Chi tiết khách hàng"
          className="min-h-[420px] rounded-card border border-line bg-surface p-4 shadow-card xl:max-h-[720px] xl:overflow-y-auto"
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

                {canEdit && !selectedAppt?.upcoming ? (
                  <button
                    type="button"
                    onClick={() => setBookOpen(true)}
                    className="flex min-h-10 w-full items-center justify-center gap-2 rounded-control bg-brand-600 px-3 text-sm font-semibold text-white hover:bg-brand-700"
                  >
                    <CalendarClock className="size-4" aria-hidden="true" />
                    Đặt lịch
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
