"use client";

import Link from "next/link";
import {
  CalendarCheck2,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Search,
  UsersRound,
} from "lucide-react";
import { useMemo, useState } from "react";

import StatCard, { StatRow } from "@/components/ui/StatCard";
import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
import { fmtDateTimeOrDate, fmtTimeOrNone } from "@/lib/datetime";
import { doctorName } from "@/lib/doctor-name";
import AppointmentActions from "./AppointmentActions";
import type { KanbanRow } from "./AppointmentsKanban";

export type AppointmentRange = "day" | "week" | "month";
type ListScope = "all" | "today" | "upcoming";

interface Stage {
  key: "pending" | "confirmed" | "completed";
  label: string;
  statuses: string[];
  dotClass: string;
  headerClass: string;
}

const STAGES: Stage[] = [
  {
    key: "pending",
    label: "Chờ xác nhận",
    statuses: ["SCHEDULED"],
    dotClass: "bg-status-ready",
    headerClass: "bg-status-ready-bg",
  },
  {
    key: "confirmed",
    label: "Đã xác nhận",
    statuses: ["CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"],
    dotClass: "bg-status-assigned",
    headerClass: "bg-status-assigned-bg",
  },
  {
    key: "completed",
    label: "Đã khám xong",
    statuses: ["COMPLETED"],
    dotClass: "bg-status-completed",
    headerClass: "bg-status-completed-bg",
  },
];

const RANGE_LABEL: Record<AppointmentRange, string> = {
  day: "Ngày",
  week: "Tuần",
  month: "Tháng",
};

const RANGE_DAYS: Record<AppointmentRange, number> = {
  day: 1,
  week: 7,
  month: 30,
};

function statusDisplay(status: string): { label: string; tone: StatusTone } {
  const map: Record<string, { label: string; tone: StatusTone }> = {
    SCHEDULED: { label: "Chờ xác nhận", tone: "ready" },
    CSKH_CONFIRMED: { label: "CSKH đã xác nhận", tone: "assigned" },
    CONFIRMED: { label: "Đã xác nhận", tone: "assigned" },
    CHECKED_IN: { label: "Đã check-in", tone: "in_progress" },
    COMPLETED: { label: "Đã khám xong", tone: "completed" },
  };
  return map[status] ?? { label: status, tone: "ready" };
}

function appointmentText(row: KanbanRow): string {
  return [
    row.patient?.full_name,
    row.patient?.patient_code,
    row.patient?.phone_primary,
    row.queue_number,
    row.service?.name,
    row.doctor?.full_name,
  ]
    .filter(Boolean)
    .join(" ")
    .toLocaleLowerCase("vi-VN");
}

function AppointmentListRow({
  row,
  active,
  onSelect,
}: {
  row: KanbanRow;
  active: boolean;
  onSelect: () => void;
}) {
  const status = statusDisplay(row.status);
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={active ? "true" : undefined}
      className={`flex w-full items-start gap-2.5 border-b border-line px-3 py-3 text-left transition-colors last:border-b-0 ${
        active
          ? "border-l-2 border-l-brand-500 bg-surface-selected"
          : "border-l-2 border-l-transparent hover:bg-surface-sunken"
      }`}
    >
      <span className="grid size-9 shrink-0 place-items-center rounded-full bg-surface-sunken text-xs font-semibold text-ink-soft">
        {row.queue_number ?? "—"}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-start justify-between gap-2">
          <span className="truncate text-sm font-semibold text-ink">
            {row.patient?.full_name ?? "Không rõ tên khách hàng"}
          </span>
          <span className="shrink-0 text-[11px] tabular-nums text-ink-muted">
            {fmtTimeOrNone(row.slot_start)}
          </span>
        </span>
        <span className="mt-0.5 block truncate font-mono text-xs text-ink-muted">
          {row.patient?.patient_code ?? "Chưa có mã khách hàng"}
        </span>
        <span className="mt-1 block truncate text-xs text-ink-soft">
          {row.service?.name ?? "Chưa chọn dịch vụ"}
        </span>
        <span className="mt-2 inline-flex">
          <StatusChip tone={status.tone} label={status.label} />
        </span>
      </span>
    </button>
  );
}

function StageColumn({
  stage,
  rows,
  selectedId,
  onSelect,
}: {
  stage: Stage;
  rows: KanbanRow[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const visible = rows.filter((row) => stage.statuses.includes(row.status));
  return (
    <section className="min-w-0 overflow-hidden rounded-control border border-line bg-surface">
      <header className={`flex items-center justify-between gap-2 border-b border-line px-3 py-2.5 ${stage.headerClass}`}>
        <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <span className={`size-2 rounded-full ${stage.dotClass}`} aria-hidden="true" />
          {stage.label}
        </h3>
        <span className="rounded-chip bg-surface px-2 py-0.5 text-xs font-semibold text-ink-muted">
          {visible.length}
        </span>
      </header>
      <div className="space-y-2 p-2">
        {visible.length > 0 ? (
          visible.map((row) => (
            <button
              key={row.id}
              type="button"
              onClick={() => onSelect(row.id)}
              aria-current={selectedId === row.id ? "true" : undefined}
              className={`w-full rounded-control border p-3 text-left transition-colors ${
                selectedId === row.id
                  ? "border-brand-500 bg-surface-selected"
                  : "border-line bg-surface hover:bg-surface-sunken"
              }`}
            >
              <span className="block truncate text-sm font-semibold text-ink">
                {row.patient?.full_name ?? "Không rõ tên khách hàng"}
              </span>
              <span className="mt-1 block truncate text-xs text-ink-muted">
                {fmtDateTimeOrDate(row.slot_start)}
              </span>
              <span className="mt-1 block truncate text-xs text-ink-soft">
                {row.service?.name ?? "Chưa chọn dịch vụ"}
              </span>
            </button>
          ))
        ) : (
          <p className="px-2 py-8 text-center text-xs text-ink-faint">Không có lịch</p>
        )}
      </div>
    </section>
  );
}

export default function AppointmentsWorkspace({
  today,
  upcoming,
  range,
  canAct,
  staffId,
}: {
  today: KanbanRow[];
  upcoming: KanbanRow[];
  range: AppointmentRange;
  canAct: boolean;
  staffId: string | null;
}) {
  const [scope, setScope] = useState<ListScope>("all");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const rows = useMemo(
    () => [
      ...today.map((row) => ({ ...row, listScope: "today" as const })),
      ...upcoming.map((row) => ({ ...row, listScope: "upcoming" as const })),
    ],
    [today, upcoming],
  );
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("vi-VN");
    return rows.filter((row) => {
      const scopeMatches = scope === "all" || row.listScope === scope;
      return scopeMatches && (!needle || appointmentText(row).includes(needle));
    });
  }, [query, rows, scope]);
  const selected = filtered.find((row) => row.id === selectedId) ?? filtered[0] ?? null;
  const status = selected ? statusDisplay(selected.status) : null;
  const actionAllowed =
    Boolean(selected) &&
    canAct &&
    selected?.status === "SCHEDULED" &&
    Boolean(staffId) &&
    selected?.doctor_id === staffId;

  const pendingCount = rows.filter((row) => row.status === "SCHEDULED").length;
  const doneCount = rows.filter((row) => row.status === "COMPLETED").length;
  const rangeHref = (entry: AppointmentRange) =>
    entry === "week" ? "/appointments" : `/appointments?range=${entry}`;

  return (
    <div className="space-y-3">
      <StatRow>
        <StatCard
          label="Lịch hôm nay"
          value={today.length}
          tone="brand"
          icon={<CalendarCheck2 className="size-5" />}
        />
        <StatCard
          label={`Sắp tới (${RANGE_DAYS[range]} ngày)`}
          value={upcoming.length}
          tone="neutral"
          icon={<CalendarClock className="size-5" />}
        />
        <StatCard
          label="Chờ xác nhận"
          value={pendingCount}
          tone="warning"
          icon={<Clock3 className="size-5" />}
        />
        <StatCard
          label="Đã khám xong"
          value={doneCount}
          tone="success"
          icon={<CheckCircle2 className="size-5" />}
        />
      </StatRow>

      <div className="flex flex-wrap items-center justify-between gap-2 rounded-card border border-line bg-surface p-3 shadow-card">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
          <label className="flex min-h-10 min-w-[240px] flex-1 items-center gap-2 rounded-control border border-line px-3 text-ink-muted lg:max-w-md">
            <Search className="size-4" aria-hidden="true" />
            <span className="sr-only">Tìm tên, mã BN hoặc số thứ tự</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Tìm tên, mã BN hoặc số thứ tự"
              className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
            />
          </label>
          <div className="flex rounded-control bg-surface-sunken p-1" role="group" aria-label="Phạm vi lịch hẹn">
            {(
              [
                ["all", "Tất cả"],
                ["today", "Hôm nay"],
                ["upcoming", "Sắp tới"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setScope(key)}
                aria-pressed={scope === key}
                className={`rounded-control px-2.5 py-1.5 text-xs font-medium ${
                  scope === key ? "bg-surface text-ink shadow-card" : "text-ink-muted hover:text-ink"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex rounded-control bg-surface-sunken p-1" role="group" aria-label="Khoảng thời gian">
          {(Object.keys(RANGE_LABEL) as AppointmentRange[]).map((entry) => (
            <Link
              key={entry}
              href={rangeHref(entry)}
              aria-current={entry === range ? "true" : undefined}
              className={`rounded-control px-2.5 py-1.5 text-xs font-medium ${
                entry === range ? "bg-surface text-ink shadow-card" : "text-ink-muted hover:text-ink"
              }`}
            >
              {RANGE_LABEL[entry]}
            </Link>
          ))}
        </div>
      </div>

      <div className="grid items-start gap-3 xl:grid-cols-[minmax(230px,0.82fr)_minmax(440px,1.55fr)_minmax(250px,0.9fr)]">
        <section
          aria-label="Danh sách lịch hẹn"
          className="overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <header className="border-b border-line px-3 py-3">
            <h2 className="text-sm font-semibold text-ink">Danh sách lịch hẹn</h2>
            <p className="mt-0.5 text-xs text-ink-muted">{filtered.length} lịch hiển thị</p>
          </header>
          <div className="max-h-[620px] overflow-y-auto">
            {filtered.length > 0 ? (
              filtered.map((row) => (
                <AppointmentListRow
                  key={row.id}
                  row={row}
                  active={selected?.id === row.id}
                  onSelect={() => setSelectedId(row.id)}
                />
              ))
            ) : (
              <p className="px-4 py-12 text-center text-sm text-ink-muted">
                Không có lịch hẹn khớp bộ lọc.
              </p>
            )}
          </div>
        </section>

        <section
          aria-label="Lịch hẹn theo trạng thái"
          className="rounded-card border border-line bg-surface p-3 shadow-card"
        >
          <div className="mb-3 flex items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-ink">Lịch hẹn theo trạng thái</h2>
              <p className="mt-0.5 text-xs text-ink-muted">
                Dữ liệu lịch thực tế trong phạm vi đang lọc.
              </p>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {STAGES.map((stage) => (
              <StageColumn
                key={stage.key}
                stage={stage}
                rows={filtered}
                selectedId={selected?.id ?? null}
                onSelect={setSelectedId}
              />
            ))}
          </div>
        </section>

        <aside
          aria-label="Thông tin lịch hẹn"
          className="rounded-card border border-line bg-surface p-4 shadow-card"
        >
          {selected && status ? (
            <>
              <div className="border-b border-line pb-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-brand-700">Thông tin lịch hẹn</p>
                    <h2 className="mt-1 truncate text-base font-semibold text-ink">
                      {selected.patient?.full_name ?? "Không rõ tên khách hàng"}
                    </h2>
                    <p className="mt-1 font-mono text-xs text-ink-muted">
                      {selected.patient?.patient_code ?? "Chưa có mã khách hàng"}
                    </p>
                  </div>
                  <StatusChip tone={status.tone} label={status.label} />
                </div>
                <p className="mt-2 text-sm text-ink-muted">
                  {selected.patient?.phone_primary ?? "Chưa có số điện thoại"}
                </p>
              </div>

              <dl className="space-y-3 py-4 text-sm">
                <Detail label="Khung giờ" value={fmtDateTimeOrDate(selected.slot_start)} />
                <Detail label="Dịch vụ" value={selected.service?.name ?? "Chưa chọn dịch vụ"} />
                <Detail
                  label="Bác sĩ"
                  value={selected.doctor?.full_name ? doctorName(selected.doctor.full_name) : "Chưa chỉ định"}
                />
                <Detail label="Kênh đặt" value={selected.booking_channel ?? "Chưa ghi nhận"} />
                <Detail label="Số thứ tự" value={selected.queue_number ?? "Chưa cấp"} />
              </dl>

              <div className="rounded-control border border-dashed border-line-strong bg-surface-muted p-3">
                <p className="text-sm font-semibold text-ink">Khung giờ và sức chứa</p>
                <p className="mt-1 text-xs text-ink-muted">
                  Chưa có dữ liệu sức chứa và giữ chỗ từ backend.
                </p>
              </div>

              {selected.clinic_patient_id ? (
                <Link
                  href={`/patients/${selected.clinic_patient_id}`}
                  className="mt-3 flex min-h-10 items-center justify-center gap-2 rounded-control border border-brand-500 bg-surface px-3 text-sm font-semibold text-brand-700 hover:bg-brand-50"
                >
                  Xem hồ sơ khách hàng
                  <ChevronRight className="size-4" aria-hidden="true" />
                </Link>
              ) : null}

              {actionAllowed ? (
                <div className="mt-3 border-t border-line pt-3">
                  <p className="mb-2 text-xs font-medium text-ink-muted">Phản hồi bác sĩ</p>
                  <AppointmentActions appointmentId={selected.id} />
                </div>
              ) : null}
            </>
          ) : (
            <div className="grid min-h-72 place-items-center text-center">
              <div>
                <UsersRound className="mx-auto size-7 text-ink-faint" aria-hidden="true" />
                <p className="mt-3 text-sm font-medium text-ink">Chưa chọn lịch hẹn</p>
                <p className="mt-1 text-xs text-ink-muted">
                  Chọn một lịch ở danh sách hoặc bảng trạng thái để xem chi tiết.
                </p>
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[5.75rem_minmax(0,1fr)] gap-2">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="min-w-0 break-words font-medium text-ink">{value}</dd>
    </div>
  );
}
