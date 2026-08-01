"use client";

// Danh sách bệnh nhân là bề mặt tra cứu: dữ liệu trong ba vùng đều lấy từ cùng
// một dòng lịch hẹn gần nhất. Không dựng sinh hiệu, bệnh sử hay nghĩa vụ giả khi
// API của màn này chưa tải chúng; người có quyền lâm sàng vẫn mở phiếu khám thật.

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  CalendarDays,
  ClipboardList,
  FileText,
  MapPin,
  Phone,
  Search,
  SlidersHorizontal,
  Stethoscope,
  UserRound,
  UsersRound,
} from "lucide-react";
import { fmtDate, fmtDateTimeOrDate } from "../../../lib/datetime";
import { unaccentVi } from "../../../lib/validation";
import ClinicalRecordForm from "../tasks/ClinicalRecordForm";
import type { DoctorApptRow } from "../tasks/DoctorWorkBoard";
import SplitPane from "../SplitPane";
import QuickBookingModal from "./QuickBookingModal";
import type { Option } from "../patients/AppointmentBooking";

export interface ExaminedRow {
  clinic_patient_id: string;
  patient_code: string;
  full_name: string;
  phone_primary: string | null;
  date_of_birth: string | null;
  gender: string | null;
  visit_count: number;
  latest: string;
  phan_loai: "Khám lần đầu" | "Tái khám";
  /** Lượt hẹn gần nhất là nguồn duy nhất của panel phải. */
  appt: DoctorApptRow;
}

type Filter = "all" | "first" | "return";

const STATUS_PRESENTATION: Record<string, { label: string; className: string }> = {
  SCHEDULED: { label: "Chưa xác nhận", className: "bg-warning-bg text-warning" },
  CSKH_CONFIRMED: { label: "Đã xác nhận", className: "bg-brand-100 text-brand-800" },
  CONFIRMED: { label: "Đã xác nhận", className: "bg-brand-100 text-brand-800" },
  CHECKED_IN: { label: "Đã check-in", className: "bg-status-assigned-bg text-status-assigned" },
  IN_PROGRESS: { label: "Đang khám", className: "bg-status-in-progress-bg text-status-in-progress" },
  COMPLETED: { label: "Đã khám xong", className: "bg-success-bg text-success" },
  NO_SHOW: { label: "Không đến", className: "bg-surface-sunken text-ink-soft" },
  CANCELLED: { label: "Đã huỷ", className: "bg-surface-sunken text-ink-soft" },
  DOCTOR_DECLINED: { label: "Bác sĩ từ chối", className: "bg-danger-bg text-danger" },
};

function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((part) => part[0]?.toLocaleUpperCase("vi-VN") ?? "")
    .join("") || "?";
}

function PatientKind({ value }: { value: ExaminedRow["phan_loai"] }) {
  const first = value === "Khám lần đầu";
  return (
    <span
      className={
        "inline-flex items-center rounded-chip px-2 py-1 text-[10px] font-semibold " +
        (first ? "bg-success-bg text-success" : "bg-warning-bg text-warning")
      }
    >
      {value}
    </span>
  );
}

function AppointmentStatus({ status }: { status: string }) {
  const presentation = STATUS_PRESENTATION[status] ?? {
    label: status,
    className: "bg-surface-sunken text-ink-soft",
  };
  return (
    <span className={`inline-flex rounded-chip px-2 py-1 text-[10px] font-semibold ${presentation.className}`}>
      {presentation.label}
    </span>
  );
}

function DetailLine({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex gap-2.5 py-2.5">
      <span className="mt-0.5 shrink-0 text-brand-600">{icon}</span>
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">{label}</p>
        <div className="mt-0.5 break-words text-sm text-ink">{value}</div>
      </div>
    </div>
  );
}

export default function PatientListView({
  rows,
  enablePopup = false,
  canEditAdmin = false,
  showPreVisitBrief = false,
  showRebook = false,
  walkinRebook = false,
  enableVisitPager = false,
  services = [],
  doctors = [],
  locations = [],
}: {
  rows: ExaminedRow[];
  /** Chỉ vai lâm sàng mở phiếu khám thật ở vùng SplitPane. */
  enablePopup?: boolean;
  canEditAdmin?: boolean;
  showPreVisitBrief?: boolean;
  showRebook?: boolean;
  walkinRebook?: boolean;
  enableVisitPager?: boolean;
  services?: Option[];
  doctors?: Option[];
  locations?: Option[];
}) {
  const router = useRouter();
  const [term, setTerm] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(rows[0]?.clinic_patient_id ?? null);
  const [openAppt, setOpenAppt] = useState<DoctorApptRow | null>(null);
  const [bookingAppt, setBookingAppt] = useState<DoctorApptRow | null>(null);

  const shown = useMemo(() => {
    const normalized = unaccentVi(term.trim());
    return rows.filter((row) => {
      if (filter === "first" && row.phan_loai !== "Khám lần đầu") return false;
      if (filter === "return" && row.phan_loai !== "Tái khám") return false;
      if (!normalized) return true;
      return (
        unaccentVi(row.full_name).includes(normalized) ||
        unaccentVi(row.patient_code).includes(normalized) ||
        unaccentVi(row.phone_primary ?? "").includes(normalized)
      );
    });
  }, [filter, rows, term]);

  // Đổi bộ lọc không được để panel tiếp tục hiện một BN đã bị lọc ra.
  const selected =
    shown.find((item) => item.clinic_patient_id === selectedId) ??
    shown[0] ??
    null;
  const firstCount = rows.filter((row) => row.phan_loai === "Khám lần đầu").length;
  const returnCount = rows.length - firstCount;
  const filters: { key: Filter; label: string }[] = [
    { key: "all", label: `Tất cả (${rows.length})` },
    { key: "first", label: `Khám lần đầu (${firstCount})` },
    { key: "return", label: `Tái khám (${returnCount})` },
  ];

  const directory = (
    <section
      aria-label="Danh sách bệnh nhân"
      className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
    >
      <div className="border-b border-line px-4 py-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold text-ink">
              <UsersRound size={16} className="text-brand-600" /> Danh sách bệnh nhân
            </p>
            <p className="mt-1 text-xs text-ink-muted">Tra cứu hồ sơ và lượt khám gần nhất</p>
          </div>
          <span className="rounded-chip bg-brand-50 px-2 py-1 text-xs font-semibold text-brand-800">
            {shown.length}
          </span>
        </div>
        <label className="relative mt-4 block">
          <Search
            size={16}
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint"
          />
          <input
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Tìm tên, mã BN hoặc SĐT"
            className="h-10 w-full rounded-control border border-line bg-white pl-9 pr-3 text-sm text-ink outline-none transition focus:border-brand-600 focus:ring-2 focus:ring-brand-600/15"
          />
        </label>
        <div className="mt-3 flex flex-wrap gap-1.5" aria-label="Lọc danh sách bệnh nhân">
          {filters.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setFilter(item.key)}
              aria-pressed={filter === item.key}
              className={
                "rounded-chip px-2.5 py-1.5 text-xs font-semibold transition-colors " +
                (filter === item.key
                  ? "bg-brand-600 text-white"
                  : "bg-surface-muted text-ink-soft hover:bg-brand-50 hover:text-brand-800")
              }
            >
              {item.label}
            </button>
          ))}
          <span className="ml-auto inline-flex items-center gap-1 px-1 text-[11px] text-ink-faint">
            <SlidersHorizontal size={12} /> Lọc cục bộ
          </span>
        </div>
      </div>

      <ul className="max-h-[62vh] divide-y divide-line overflow-y-auto" aria-label="Kết quả tìm bệnh nhân">
        {shown.length === 0 ? (
          <li className="px-5 py-12 text-center text-sm text-ink-muted">
            Không tìm thấy bệnh nhân phù hợp.
          </li>
        ) : (
          shown.map((row) => {
            const active = selected?.clinic_patient_id === row.clinic_patient_id;
            return (
              <li key={row.clinic_patient_id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(row.clinic_patient_id)}
                  aria-pressed={active}
                  className={
                    "flex w-full items-start gap-3 px-4 py-3.5 text-left transition-colors " +
                    (active
                      ? "border-l-[3px] border-brand-600 bg-surface-selected pl-[13px]"
                      : "border-l-[3px] border-transparent hover:bg-surface-muted")
                  }
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-800">
                    {initials(row.full_name)}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-start justify-between gap-2">
                      <span className="truncate text-sm font-semibold text-ink">{row.full_name}</span>
                      <PatientKind value={row.phan_loai} />
                    </span>
                    <span className="mt-1 block truncate font-mono text-[11px] text-ink-muted">
                      {row.patient_code}
                    </span>
                    <span className="mt-1 flex items-center justify-between gap-2 text-[11px] text-ink-muted">
                      <span className="truncate">{row.phone_primary ?? "Chưa có SĐT"}</span>
                      <span className="shrink-0">{fmtDate(row.latest)}</span>
                    </span>
                  </span>
                </button>
              </li>
            );
          })
        )}
      </ul>
      <div className="border-t border-line px-4 py-3 text-xs text-ink-muted">
        Hiển thị {shown.length} trên {rows.length} hồ sơ đã có lượt khám
      </div>
    </section>
  );

  const overview = (
    <section
      aria-label="Tổng quan hồ sơ"
      className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
    >
      {selected ? (
        <>
          <header className="border-b border-line px-5 py-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-800">
                  {initials(selected.full_name)}
                </span>
                <div className="min-w-0">
                  <h2 className="truncate text-lg font-semibold text-ink">{selected.full_name}</h2>
                  <p className="mt-0.5 truncate font-mono text-xs text-ink-muted">{selected.patient_code}</p>
                </div>
              </div>
              <PatientKind value={selected.phan_loai} />
            </div>
            <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
              <span>{selected.date_of_birth ? `Ngày sinh ${selected.date_of_birth}` : "Chưa có ngày sinh"}</span>
              <span>{selected.gender ?? "Chưa có giới tính"}</span>
              <span>{selected.visit_count} lượt khám</span>
            </div>
          </header>

          <div className="grid gap-3 p-5 sm:grid-cols-2">
            <article className="rounded-control border border-line bg-surface-muted p-3.5">
              <p className="flex items-center gap-2 text-xs font-semibold text-ink-soft">
                <UserRound size={14} className="text-brand-600" /> Thông tin liên hệ
              </p>
              <div className="mt-2 space-y-1.5 text-sm text-ink">
                <p className="flex items-center gap-2"><Phone size={13} className="text-ink-muted" /> {selected.phone_primary ?? "Chưa có SĐT"}</p>
                <p className="flex items-center gap-2"><MapPin size={13} className="text-ink-muted" /> Địa chỉ xem trong hồ sơ</p>
              </div>
            </article>
            <article className="rounded-control border border-line bg-surface-muted p-3.5">
              <p className="flex items-center gap-2 text-xs font-semibold text-ink-soft">
                <ClipboardList size={14} className="text-brand-600" /> Lịch sử ghi nhận
              </p>
              <p className="mt-2 text-sm text-ink">Lần gần nhất: {fmtDateTimeOrDate(selected.latest)}</p>
              <p className="mt-1 text-xs text-ink-muted">{selected.visit_count} lượt trong danh sách đã tải</p>
            </article>
          </div>

          <section className="border-t border-line px-5 py-4">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-ink">Lượt khám gần nhất</h3>
              <AppointmentStatus status={selected.appt.status} />
            </div>
            <div className="mt-3 grid gap-2 rounded-control border border-line p-3.5 text-sm sm:grid-cols-2">
              <p><span className="text-ink-muted">Thời gian:</span> {fmtDateTimeOrDate(selected.appt.slot_start)}</p>
              <p><span className="text-ink-muted">Dịch vụ:</span> {selected.appt.service?.name ?? "Chưa có dữ liệu"}</p>
              <p><span className="text-ink-muted">Số thứ tự:</span> {selected.appt.queue_number ?? "Chưa được cấp"}</p>
              <p><span className="text-ink-muted">Kênh:</span> {selected.appt.booking_channel ?? "Chưa ghi nhận"}</p>
            </div>
          </section>

          <div className="border-t border-line px-5 py-4">
            {enablePopup ? (
              <button
                type="button"
                onClick={() => setOpenAppt(selected.appt)}
                className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-control border border-brand-600 bg-white px-4 py-2 text-sm font-semibold text-brand-700 transition hover:bg-brand-50 sm:w-auto"
              >
                <FileText size={16} /> Mở hồ sơ khám
              </button>
            ) : (
              <Link
                href={`/patients/${selected.clinic_patient_id}`}
                className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-control border border-brand-600 bg-white px-4 py-2 text-sm font-semibold text-brand-700 transition hover:bg-brand-50 sm:w-auto"
              >
                <FileText size={16} /> Mở hồ sơ khám
              </Link>
            )}
          </div>
        </>
      ) : (
        <div className="flex min-h-[360px] flex-col items-center justify-center px-5 text-center">
          <UserRound size={32} className="text-ink-faint" />
          <p className="mt-3 text-sm font-medium text-ink">Chưa chọn bệnh nhân</p>
          <p className="mt-1 text-xs text-ink-muted">Chọn một hồ sơ ở cột danh sách để xem thông tin.</p>
        </div>
      )}
    </section>
  );

  const visitPanel = (
    <aside
      aria-label="Lượt khám gần nhất"
      className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
    >
      <header className="border-b border-line px-4 py-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Stethoscope size={16} className="text-brand-600" /> Thông tin lượt khám
        </p>
        <p className="mt-1 text-xs text-ink-muted">Chỉ hiển thị dữ liệu đã có từ lịch hẹn</p>
      </header>
      {selected ? (
        <div className="divide-y divide-line px-4">
          <DetailLine icon={<CalendarDays size={15} />} label="Thời gian hẹn" value={fmtDateTimeOrDate(selected.appt.slot_start)} />
          <DetailLine icon={<Stethoscope size={15} />} label="Dịch vụ" value={selected.appt.service?.name ?? "Chưa có dữ liệu dịch vụ"} />
          <DetailLine icon={<UsersRound size={15} />} label="Loại hồ sơ" value={selected.phan_loai} />
          <DetailLine icon={<ArrowRight size={15} />} label="Trạng thái lịch" value={<AppointmentStatus status={selected.appt.status} />} />
          <div className="py-4">
            <p className="rounded-control bg-surface-muted p-3 text-xs leading-relaxed text-ink-muted">
              Hành trình, sinh hiệu và kết quả lâm sàng chỉ hiển thị trong phiếu khám khi vai trò của bạn được cấp quyền.
            </p>
          </div>
          <Link
            href={`/patients/${selected.clinic_patient_id}`}
            className="mb-4 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-control bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-700"
          >
            Xem thông tin hành chính <ArrowRight size={16} />
          </Link>
        </div>
      ) : (
        <p className="px-4 py-10 text-center text-sm text-ink-muted">Chưa có lượt khám để hiển thị.</p>
      )}
    </aside>
  );

  if (openAppt) {
    return (
      <>
        <p className="mb-2 text-xs text-ink-muted">Kéo thanh phân cách để đổi độ rộng hai vùng làm việc.</p>
        <SplitPane
          className="md:h-[78vh]"
          initialLeftPct={42}
          left={directory}
          right={
            <ClinicalRecordForm
              key={openAppt.id}
              appt={openAppt}
              staffId={null}
              fill
              readOnly
              canEditAdmin={canEditAdmin}
              showPreVisitBrief={showPreVisitBrief}
              showRebook={showRebook}
              enableVisitPager={enableVisitPager}
              onRebook={() => setBookingAppt(openAppt)}
              onClose={() => setOpenAppt(null)}
            />
          }
        />
        {bookingAppt?.patient && (
          <QuickBookingModal
            patient={bookingAppt.patient}
            services={services}
            doctors={doctors}
            locations={locations}
            walkin={walkinRebook}
            onClose={() => setBookingAppt(null)}
            onBooked={() => {
              setBookingAppt(null);
              router.refresh();
            }}
          />
        )}
      </>
    );
  }

  return (
    <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(250px,0.82fr)_minmax(380px,1.42fr)_minmax(250px,0.8fr)]">
      {directory}
      {overview}
      {visitPanel}
    </div>
  );
}
