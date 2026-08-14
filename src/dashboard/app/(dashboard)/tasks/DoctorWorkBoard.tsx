"use client";

// Workspace khám bệnh. Hàng đợi vẫn lấy từ appointment và mở đúng
// ClinicalRecordForm cũ; thay đổi ở đây chỉ là cấu trúc hiển thị V2.

import { useState } from "react";
import {
  CalendarDays,
  ClipboardList,
  FileText,
  FlaskConical,
  Printer,
  Search,
  Stethoscope,
  UsersRound,
} from "lucide-react";

import { fmtTimeOrNone } from "../../../lib/datetime";
import {
  currentWeekStartVn,
  dayLabel,
  fmtDayMonth,
  shiftWeek,
  todayVn,
  weekDates,
} from "../../../lib/roster";
import { daysInMonth } from "../../../lib/validation";
import StatusBadge from "../StatusBadge";
import ClinicalRecordForm from "./ClinicalRecordForm";
import {
  EmptyWorkspace,
  Monogram,
  PanelHeading,
  WorkspaceMetric,
  WorkspaceMetricRow,
} from "./WorkspacePrimitives";
import workspaceStyles from "./WorkspacePrimitives.module.css";
import { laKhamMoi, nhanPhanLoaiKham } from "../../../lib/phan-loai-kham";

export interface DoctorApptRow {
  id: string;
  slot_start: string;
  status: string;
  /** Số thứ tự khám (queue_number) — lễ tân cấp khi check-in. */
  queue_number?: string | null;
  /** "Khám lần đầu" | "Tái khám" | "" — suy từ lịch sử hẹn (server tính sẵn). */
  phan_loai?: string;
  /** THỨ TỰ GỌI — backend tính (services/queue_order.py). Màn hình chỉ xếp
   *  theo con số này, không tự tính lại. Trước đây mỗi màn gọi compareQueue()
   *  từ một bản chép của luật bằng TypeScript. */
  call_order?: number | null;
  /** Làn: -2 ƯT · -1 chờ đọc KQ · 0 có hẹn đúng giờ · 1 vãng lai/đến muộn */
  call_tier?: number | null;
  /** UU_TIEN | CHO_DOC_KQ | DAT_TRUOC_DUNG_GIO | DEN_TRUC_TIEP | DEN_TRE | CHUA_DEN */
  call_reason?: string | null;
  /** Có người đến TRƯỚC mà bị xếp SAU mình — chỗ cần một câu giải thích. */
  promoted?: boolean;
  promoted_over?: number;
  patient: {
    clinic_patient_id: string;
    patient_code: string;
    full_name: string;
    date_of_birth: string | null;
    phone_primary: string | null;
    phone_secondary: string | null;
    gender: string | null;
    ethnicity: string | null;
    nationality: string | null;
    occupation: string | null;
    patient_objection: string | null;
    address: string | null;
    guardian_name: string | null;
  } | null;
  service: {
    name: string;
    /** Mã phiếu khám chuyên khoa, backend CHỌN SẴN theo giới bệnh nhân
     *  (khám tiền hôn nhân: nữ ra PK, nam ra NK). `null` = dịch vụ này không
     *  có phiếu riêng — màn hình phải NÓI RA, không được ẩn im lặng.
     *
     *  KHÔNG BẮT BUỘC vì hai màn khác (lưới tuần ở Trang chủ, Danh sách bệnh
     *  nhân) dựng dòng từ truy vấn riêng chưa mang cột này. Thiếu nó thì rơi
     *  về cách đoán cũ theo tên dịch vụ — kém hơn, nhưng không vỡ. */
    form_code?: string | null;
  } | null;
  /** Kênh đặt — "WALK_IN" = vãng lai; còn lại = đặt hẹn online. */
  booking_channel?: string | null;
  /** Mốc giờ đến thật (visit.checked_in_at). */
  checked_in_at?: string | null;
  /** Đã có KQ lab về hết → chờ bác sĩ đọc. */
  b3_ready?: boolean | null;
}

const STATUS_GROUPS: { key: string; label: string; statuses: string[] }[] = [
  { key: "all", label: "Tất cả", statuses: [] },
  { key: "pending", label: "Chờ xác nhận", statuses: ["SCHEDULED", "CSKH_CONFIRMED"] },
  { key: "confirmed", label: "Đã xác nhận / đến", statuses: ["CONFIRMED", "CHECKED_IN"] },
  { key: "done", label: "Đã khám xong", statuses: ["COMPLETED"] },
  { key: "off", label: "Từ chối / Hủy", statuses: ["DOCTOR_DECLINED", "CANCELLED", "NO_SHOW"] },
];

const PERIODS: { key: string; label: string }[] = [
  { key: "all", label: "Tất cả" },
  { key: "today", label: "Hôm nay" },
  { key: "week", label: "Tuần này" },
  { key: "next", label: "Tuần sau" },
  { key: "month", label: "Tháng này" },
];

function PhanLoai({ value }: { value?: string }) {
  if (!value) return <span className="text-ink-faint">Chưa phân loại</span>;
  const first = laKhamMoi(value);
  return (
    <span
      className={`inline-flex rounded-chip px-2 py-0.5 text-xs font-medium ${
        first ? "bg-success-bg text-success" : "bg-warning-bg text-warning"
      }`}
    >
      {nhanPhanLoaiKham(value)}
    </span>
  );
}

function dateInVn(iso: string): string {
  return new Date(new Date(iso).getTime() + 7 * 3_600_000).toISOString().slice(0, 10);
}

function patientMeta(row: DoctorApptRow): string {
  const bits = [row.patient?.patient_code, row.patient?.phone_primary].filter(Boolean);
  return bits.length ? bits.join(" · ") : "Chưa có dữ liệu liên hệ";
}

function QueueRow({
  row,
  selected,
  onSelect,
}: {
  row: DoctorApptRow;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      className={`w-full border-l-[3px] px-3 py-3 text-left transition-colors ${
        selected
          ? "border-brand-500 bg-surface-selected"
          : "border-transparent bg-surface hover:bg-surface-sunken"
      }`}
    >
      <span className="flex items-start gap-2.5">
        <Monogram value={row.patient?.full_name} />
        <span className="min-w-0 flex-1">
          <span className="flex items-center justify-between gap-2">
            <span className="truncate text-sm font-semibold text-ink">
              {row.patient?.full_name ?? "Chưa rõ tên"}
            </span>
            <span className="shrink-0 text-xs tabular-nums text-ink-muted">
              {fmtTimeOrNone(row.slot_start)}
            </span>
          </span>
          <span className="mt-0.5 block truncate text-xs text-ink-muted">
            {patientMeta(row)}
          </span>
          <span className="mt-1 flex items-center justify-between gap-2">
            <span className="truncate text-xs text-ink-faint">
              {row.service?.name ?? "Chưa có dịch vụ"}
            </span>
            {row.queue_number ? (
              <span className="shrink-0 rounded-chip bg-surface-sunken px-1.5 py-0.5 text-[11px] font-medium text-ink-soft">
                {row.queue_number}
              </span>
            ) : null}
          </span>
          {row.b3_ready ? (
            <span className="mt-1 inline-flex rounded-chip bg-warning-bg px-1.5 py-0.5 text-[11px] font-medium text-warning">
              Chờ đọc kết quả
            </span>
          ) : null}
        </span>
      </span>
    </button>
  );
}

function SelectedPatientSummary({ row }: { row: DoctorApptRow }) {
  return (
    <div className="border-b border-line px-4 py-3.5">
      <div className="flex items-start gap-3">
        <Monogram value={row.patient?.full_name} className="size-11 text-sm" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-base font-semibold text-ink">
                {row.patient?.full_name ?? "Chưa rõ tên người bệnh"}
              </p>
              <p className="mt-0.5 text-xs text-ink-muted">{patientMeta(row)}</p>
            </div>
            <StatusBadge status={row.status} />
          </div>
          <div className="mt-3 grid gap-2 text-xs text-ink-muted sm:grid-cols-3">
            <span>
              <span className="block text-ink-faint">Dịch vụ</span>
              <span className="mt-0.5 block truncate font-medium text-ink-soft">
                {row.service?.name ?? "Chưa có dữ liệu"}
              </span>
            </span>
            <span>
              <span className="block text-ink-faint">Lịch hẹn</span>
              <span className="mt-0.5 block font-medium text-ink-soft">
                {dayLabel(dateInVn(row.slot_start))} · {fmtTimeOrNone(row.slot_start)}
              </span>
            </span>
            <span>
              <span className="block text-ink-faint">Số thứ tự</span>
              <span className="mt-0.5 block font-medium text-ink-soft">
                {row.queue_number ?? "Chưa được cấp"}
              </span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DoctorWorkBoard({
  rows,
  staffId,
  readOnly = false,
  canEditAdmin = false,
  showPreVisitBrief = false,
  showSono = false,
  vitalsOnly = false,
}: {
  rows: DoctorApptRow[];
  staffId: string | null;
  /** Vai vận hành: chỉ xem lịch, không mount hồ sơ lâm sàng. */
  readOnly?: boolean;
  /** Cho sửa mục I Hành chính trong hồ sơ lâm sàng. */
  canEditAdmin?: boolean;
  /** Hiện nút tóm tắt trước khám — chỉ BÁC SĨ bật từ server. */
  showPreVisitBrief?: boolean;
  /** Hiện form số đo siêu âm thai — chỉ Bác sĩ Siêu âm bật theo vai. */
  showSono?: boolean;
  vitalsOnly?: boolean;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [period, setPeriod] = useState("today");
  const [statusFilter, setStatusFilter] = useState("all");
  const [query, setQuery] = useState("");

  // Operational viewers never receive the clinical form even if a stale client
  // state still holds an appointment id.
  const open = readOnly ? null : (rows.find((a) => a.id === openId) ?? null);

  const today = todayVn();
  const week = weekDates(currentWeekStartVn());
  const nextWeek = weekDates(shiftWeek(currentWeekStartVn(), 1));
  const monthStart = `${today.slice(0, 7)}-01`;
  const monthEnd = `${today.slice(0, 7)}-${String(
    daysInMonth(Number(today.slice(5, 7)), Number(today.slice(0, 4))),
  ).padStart(2, "0")}`;
  const ranges: Record<string, [string, string] | null> = {
    all: null,
    today: [today, today],
    week: [week[0], week[6]],
    next: [nextWeek[0], nextWeek[6]],
    month: [monthStart, monthEnd],
  };
  const range = ranges[period];
  const statusGroup = STATUS_GROUPS.find((group) => group.key === statusFilter);
  const normalizedQuery = query.trim().toLocaleLowerCase("vi-VN");
  const periodRows = rows.filter((row) => {
    const date = dateInVn(row.slot_start);
    return !(range && (date < range[0] || date > range[1]));
  });
  const visible = periodRows
    .filter((row) => {
      if (statusGroup?.statuses.length && !statusGroup.statuses.includes(row.status)) {
        return false;
      }
      if (!normalizedQuery) return true;
      return [
        row.patient?.full_name,
        row.patient?.patient_code,
        row.queue_number,
        row.service?.name,
      ]
        .filter(Boolean)
        .some((value) => value?.toLocaleLowerCase("vi-VN").includes(normalizedQuery));
    })
    .sort((a, b) => {
      const dateA = dateInVn(a.slot_start);
      const dateB = dateInVn(b.slot_start);
      if (dateA !== dateB) return dateA < dateB ? -1 : 1;
      // Thứ tự gọi do BACKEND quyết (services/queue_order.py). Trước đây màn
      // này gọi compareQueue() từ một bản chép của luật bằng TypeScript — hai
      // bản giống nhau cho tới ngày ai đó sửa một bên.
      return (a.call_order ?? 0) - (b.call_order ?? 0);
    });
  const selected = visible.find((row) => row.id === selectedId) ?? visible[0] ?? null;

  const waitingCount = periodRows.filter((row) => row.status === "CHECKED_IN").length;
  const scheduledCount = periodRows.filter((row) =>
    ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"].includes(row.status),
  ).length;
  const completedCount = periodRows.filter((row) => row.status === "COMPLETED").length;
  const b3Count = periodRows.filter((row) => row.b3_ready).length;

  if (open) {
    return (
      <section className="rounded-card border border-line bg-surface shadow-panel" aria-label="Hồ sơ lâm sàng đang mở">
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <div>
            <p className="text-sm font-semibold text-ink">Hồ sơ lâm sàng</p>
            <p className="mt-0.5 text-xs text-ink-muted">
              {open.patient?.full_name ?? "Người bệnh chưa rõ tên"}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setOpenId(null)}
            className="rounded-control border border-line bg-surface px-3 py-2 text-xs font-medium text-ink-soft hover:bg-surface-sunken"
          >
            Quay lại hàng đợi
          </button>
        </div>
        <ClinicalRecordForm
          key={open.id}
          appt={open}
          staffId={staffId}
          fill
          readOnly={readOnly}
          vitalsOnly={vitalsOnly}
          canEditAdmin={canEditAdmin}
          showPreVisitBrief={showPreVisitBrief}
          // Bác sĩ mới ký được. `showPreVisitBrief` đã do server bật đúng theo
          // isDoctorRole, nên nó là tín hiệu sẵn có chính xác nhất ở đây.
          canSign={showPreVisitBrief}
          showSono={showSono}
          enableVisitPager
          onClose={() => setOpenId(null)}
        />
      </section>
    );
  }

  return (
    <div className="space-y-4">
      <WorkspaceMetricRow>
        <WorkspaceMetric
          label="Lịch trong kỳ"
          value={visible.length}
          icon={<CalendarDays className="size-5" />}
          tone="brand"
          detail={PERIODS.find((item) => item.key === period)?.label}
        />
        <WorkspaceMetric
          label="Chờ lễ tân / bác sĩ"
          value={scheduledCount}
          icon={<UsersRound className="size-5" />}
          tone="warning"
        />
        <WorkspaceMetric
          label="Đã check-in"
          value={waitingCount}
          icon={<Stethoscope className="size-5" />}
          tone="brand"
        />
        <WorkspaceMetric
          label="Chờ đọc kết quả"
          value={b3Count}
          icon={<FlaskConical className="size-5" />}
          tone={b3Count ? "warning" : "neutral"}
          detail={`${completedCount} lượt đã khám xong`}
        />
      </WorkspaceMetricRow>

      <div className={workspaceStyles.workspace}>
      <div className={`${workspaceStyles.threeColumn} ${workspaceStyles.doctor}`}>
        <aside
          aria-label="Hàng đợi khám bệnh"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading title="Hàng đợi hôm nay" detail={`${visible.length} lượt theo bộ lọc`} />
          <div className="space-y-3 border-b border-line p-3">
            <label className="flex items-center gap-2 rounded-control border border-line bg-surface px-3 py-2 text-ink-muted focus-within:border-brand-500">
              <Search className="size-4 shrink-0" aria-hidden="true" />
              <span className="sr-only">Tìm bệnh nhân hoặc mã hồ sơ</span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Tìm bệnh nhân, mã hồ sơ"
                className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
              />
            </label>
            <div className="flex flex-wrap gap-1.5" aria-label="Lọc kỳ khám">
              {PERIODS.map((item) => (
                <button
                  type="button"
                  key={item.key}
                  onClick={() => setPeriod(item.key)}
                  aria-pressed={period === item.key}
                  className={`rounded-chip px-2 py-1 text-xs font-medium transition-colors ${
                    period === item.key
                      ? "bg-brand-600 text-white"
                      : "bg-surface-sunken text-ink-muted hover:bg-brand-50 hover:text-brand-800"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <div className="max-h-[620px] overflow-y-auto">
            {visible.length ? (
              visible.map((row) => (
                <QueueRow
                  key={row.id}
                  row={row}
                  selected={row.id === selected?.id}
                  onSelect={() => setSelectedId(row.id)}
                />
              ))
            ) : (
              <EmptyWorkspace
                title="Không có lượt phù hợp"
                detail="Thử đổi kỳ, trạng thái hoặc từ khóa tìm kiếm."
                icon={<UsersRound className="size-6" />}
              />
            )}
          </div>
        </aside>

        <section
          aria-label="Lịch khám và hồ sơ"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading
            title="Lịch khám và hồ sơ"
            detail="Chọn người bệnh để xem thông tin có sẵn trước khi mở hồ sơ lâm sàng."
          />
          {selected ? (
            <>
              <SelectedPatientSummary row={selected} />
              <div className="border-b border-line bg-surface-muted px-4 py-3">
                <div className="flex items-start gap-2">
                  <ClipboardList className="mt-0.5 size-4 shrink-0 text-brand-600" aria-hidden="true" />
                  <div>
                    <p className="text-xs font-medium text-ink-soft">Hồ sơ lâm sàng</p>
                    <p className="mt-0.5 text-xs leading-5 text-ink-muted">
                      Nội dung khám, sinh hiệu và chỉ định được mở trong hồ sơ chuyên sâu
                      để giữ đúng nguồn dữ liệu và quyền theo vai trò.
                    </p>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="p-4">
              <EmptyWorkspace
                title="Chưa có người bệnh được chọn"
                detail="Hàng đợi chưa có lượt khám phù hợp với bộ lọc hiện tại."
                icon={<Stethoscope className="size-7" />}
              />
            </div>
          )}

          <div className="max-h-[430px] overflow-auto">
            <table className="w-full min-w-[600px] border-collapse text-left text-xs">
              <thead className="sticky top-0 z-10 bg-surface-muted text-ink-muted">
                <tr>
                  <th className="border-b border-line px-3 py-2 font-semibold">Ngày</th>
                  <th className="border-b border-line px-3 py-2 font-semibold">Giờ</th>
                  <th className="border-b border-line px-3 py-2 font-semibold">Bệnh nhân</th>
                  <th className="border-b border-line px-3 py-2 font-semibold">Phân loại</th>
                  <th className="border-b border-line px-3 py-2 font-semibold">Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr
                    key={row.id}
                    className={row.id === selected?.id ? "bg-surface-selected" : "hover:bg-surface-muted"}
                  >
                    <td className="border-b border-line px-3 py-2.5 text-ink-soft">
                      {dayLabel(dateInVn(row.slot_start))} · {fmtDayMonth(dateInVn(row.slot_start))}
                    </td>
                    <td className="border-b border-line px-3 py-2.5 tabular-nums text-ink-soft">
                      {fmtTimeOrNone(row.slot_start)}
                    </td>
                    <td className="border-b border-line px-3 py-2.5">
                      <button
                        type="button"
                        onClick={() => setSelectedId(row.id)}
                        className="text-left font-medium text-ink hover:text-brand-700"
                      >
                        {row.patient?.full_name ?? "Chưa rõ tên"}
                      </button>
                      <span className="mt-0.5 block text-ink-faint">{row.service?.name ?? "Chưa có dịch vụ"}</span>
                    </td>
                    <td className="border-b border-line px-3 py-2.5"><PhanLoai value={row.phan_loai} /></td>
                    <td className="border-b border-line px-3 py-2.5"><StatusBadge status={row.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <aside
          aria-label="Điều phối lượt khám"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading title="Việc còn thiếu & điều phối" detail="Thông tin hiển thị từ lịch hẹn hiện có." />
          {selected ? (
            <div className="space-y-4 p-3.5">
              <section className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Lượt khám hiện tại</h3>
                <dl className="space-y-2 rounded-control border border-line bg-surface-muted p-3 text-xs">
                  <div className="flex justify-between gap-3"><dt className="text-ink-muted">Số thứ tự</dt><dd className="font-medium text-ink">{selected.queue_number ?? "Chưa cấp"}</dd></div>
                  <div className="flex justify-between gap-3"><dt className="text-ink-muted">Đã check-in</dt><dd className="font-medium text-ink">{selected.checked_in_at ? fmtTimeOrNone(selected.checked_in_at) : "Chưa có mốc"}</dd></div>
                  <div className="flex justify-between gap-3"><dt className="text-ink-muted">Kết quả cận lâm sàng</dt><dd className="font-medium text-ink">{selected.b3_ready ? "Đã sẵn sàng đọc" : "Chưa có tín hiệu"}</dd></div>
                </dl>
              </section>
              <section className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Thao tác</h3>
                {readOnly ? (
                  <p className="rounded-control border border-dashed border-line-strong bg-surface-muted px-3 py-3 text-xs leading-5 text-ink-muted">
                    Vai trò hiện tại chỉ được xem lịch, không mở hồ sơ lâm sàng.
                  </p>
                ) : (
                  <button
                    type="button"
                    onClick={() => setOpenId(selected.id)}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-control bg-brand-600 px-3 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"
                  >
                    <FileText className="size-4" /> Mở hồ sơ lâm sàng
                  </button>
                )}
                {selected.status === "COMPLETED" ? (
                  <a
                    href={`/print/${selected.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex w-full items-center justify-center gap-2 rounded-control border border-success bg-surface px-3 py-2.5 text-sm font-semibold text-success hover:bg-success-bg"
                  >
                    <Printer className="size-4" /> In phiếu khám
                  </a>
                ) : null}
              </section>
              {showSono ? (
                <p className="rounded-control border border-brand-100 bg-brand-50 px-3 py-2.5 text-xs leading-5 text-brand-800">
                  Vai trò này có biểu mẫu số đo siêu âm trong hồ sơ lâm sàng.
                </p>
              ) : null}
            </div>
          ) : (
            <div className="p-3.5">
              <EmptyWorkspace
                title="Chưa có lượt để điều phối"
                detail="Chọn một người bệnh từ hàng đợi để xem tình trạng thực tế."
              />
            </div>
          )}
        </aside>
      </div>
      </div>

      <div className="flex flex-wrap gap-1.5" aria-label="Lọc trạng thái lịch khám">
        {STATUS_GROUPS.map((group) => (
          <button
            type="button"
            key={group.key}
            onClick={() => setStatusFilter(group.key)}
            aria-pressed={statusFilter === group.key}
            className={`rounded-chip border px-2.5 py-1 text-xs font-medium transition-colors ${
              statusFilter === group.key
                ? "border-brand-600 bg-brand-50 text-brand-800"
                : "border-line bg-surface text-ink-muted hover:bg-surface-sunken"
            }`}
          >
            {group.label}
          </button>
        ))}
      </div>
    </div>
  );
}
