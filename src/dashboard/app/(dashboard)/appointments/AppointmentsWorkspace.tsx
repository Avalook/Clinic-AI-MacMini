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
import { fmtDateTimeOrDate, fmtTimeOrNone, slotRange } from "@/lib/datetime";
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
  const timeStr = row.slot_start ? slotRange(new Date(row.slot_start).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", hour12: false }), 60) : "—";
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
            {timeStr}
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

import CskhBookingGrid from "./CskhBookingGrid";

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
  return <CskhBookingGrid />;
}
