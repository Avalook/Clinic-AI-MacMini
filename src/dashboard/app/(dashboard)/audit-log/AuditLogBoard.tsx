"use client";

import { useMemo, useState } from "react";
import StatCard, { StatRow } from "@/components/ui/StatCard";
import { Activity, Users, Calendar, AlertCircle, Copy, ExternalLink, Search } from "lucide-react";
import { fmtTime, fmtDate } from "../../../lib/datetime";

interface AuditEvent {
  event_id: string;
  event_type: string;
  aggregate_type: string;
  aggregate_id: string;
  payload: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
  source: string;
  occurred_at: string;
}

interface Props {
  events: AuditEvent[];
}

type AuditTab = "all" | "patient" | "appointment" | "task" | "system";

const TABS: { key: AuditTab; label: string }[] = [
  { key: "all", label: "Tất cả" },
  { key: "patient", label: "Khách hàng" },
  { key: "appointment", label: "Lịch hẹn" },
  { key: "task", label: "Công việc" },
  { key: "system", label: "Hệ thống" },
];

function aggregateToTab(agg: string): AuditTab {
  if (agg === "patient" || agg === "clinic_patient") return "patient";
  if (agg === "appointment") return "appointment";
  if (agg === "cskh_action" || agg === "staff_task") return "task";
  return "system";
}

function eventLabel(type: string): string {
  const map: Record<string, string> = {
    "appointment.created": "Tạo lịch hẹn",
    "appointment.confirmed": "Xác nhận lịch hẹn",
    "appointment.cancelled": "Hủy lịch hẹn",
    "appointment.checked_in": "Check-in",
    "appointment.completed": "Khám xong",
    "appointment.updated": "Cập nhật lịch hẹn",
    "appointment.declined": "Bác sĩ từ chối",
    "patient.created": "Tạo bệnh nhân",
    "patient.updated": "Cập nhật thông tin KH",
    "cskh_action.created": "Tạo công việc chăm sóc",
    "cskh_action.updated": "Cập nhật bước tiếp theo",
    "staff_task.completed": "Hoàn thành công việc",
    "visit.created": "Tạo lượt khám",
    "visit.completed": "Hoàn thành lượt khám",
  };
  return map[type] ?? type;
}

/** Extract before/after diff from event payload */
function extractChanges(
  payload: Record<string, unknown> | null,
): { field: string; before: string; after: string }[] {
  if (!payload) return [];
  const changes: { field: string; before: string; after: string }[] = [];

  if (payload.changes && typeof payload.changes === "object") {
    const ch = payload.changes as Record<
      string,
      { old?: unknown; new?: unknown }
    >;
    for (const [field, val] of Object.entries(ch)) {
      changes.push({
        field,
        before: val?.old != null ? String(val.old) : "—",
        after: val?.new != null ? String(val.new) : "—",
      });
    }
  } else if (payload.before && payload.after) {
    const before = payload.before as Record<string, unknown>;
    const after = payload.after as Record<string, unknown>;
    const allKeys = new Set([...Object.keys(before), ...Object.keys(after)]);
    for (const key of allKeys) {
      const b = before[key];
      const a = after[key];
      if (JSON.stringify(b) !== JSON.stringify(a)) {
        changes.push({
          field: key,
          before: b != null ? String(b) : "—",
          after: a != null ? String(a) : "—",
        });
      }
    }
  } else {
    const skip = new Set(["staff_name", "staff_id", "patient_name", "patient_id"]);
    for (const [key, val] of Object.entries(payload)) {
      if (skip.has(key) || val == null) continue;
      if (typeof val === "object") continue;
      changes.push({ field: key, before: "—", after: String(val) });
    }
  }
  return changes.slice(0, 10);
}

const FIELD_LABELS: Record<string, string> = {
  status: "Trạng thái",
  slot_start: "Khung giờ",
  doctor_id: "Bác sĩ",
  service_type_id: "Dịch vụ",
  full_name: "Họ tên",
  phone_primary: "SĐT",
  booking_channel: "Kênh đặt",
  location_id: "Cơ sở",
  step: "Bước",
  category: "Loại",
  description: "Mô tả",
};

export default function AuditLogBoard({ events }: Props) {
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<AuditTab>("all");
  const [selId, setSelId] = useState<string | null>(events[0]?.event_id ?? null);

  const sel = events.find((e) => e.event_id === selId) ?? events[0] ?? null;

  const uniqueSources = useMemo(
    () => new Set(events.map((e) => String(e.payload?.staff_name ?? e.source))).size,
    [events],
  );
  const apptEvents = useMemo(
    () => events.filter((e) => e.aggregate_type === "appointment").length,
    [events],
  );
  const alertEvents = useMemo(
    () =>
      events.filter(
        (e) =>
          e.event_type.includes("declined") ||
          e.event_type.includes("cancelled") ||
          e.event_type.includes("error"),
      ).length,
    [events],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return events.filter((e) => {
      if (tab !== "all" && aggregateToTab(e.aggregate_type) !== tab) return false;
      if (!q) return true;
      return (
        e.event_type.toLowerCase().includes(q) ||
        e.aggregate_type.toLowerCase().includes(q) ||
        e.source.toLowerCase().includes(q) ||
        String(e.payload?.staff_name ?? "").toLowerCase().includes(q) ||
        String(e.payload?.patient_name ?? "").toLowerCase().includes(q) ||
        JSON.stringify(e.payload ?? {}).toLowerCase().includes(q)
      );
    });
  }, [events, search, tab]);

  const changes = sel ? extractChanges(sel.payload) : [];

  return (
    <div className="space-y-4">
      <StatRow>
        <StatCard label="Sự kiện hôm nay" value={events.length} tone="brand" icon={<Activity className="size-5" />} />
        <StatCard label="Người dùng hoạt động" value={uniqueSources} tone="success" icon={<Users className="size-5 text-success" />} />
        <StatCard label="Thay đổi lịch hẹn" value={apptEvents} tone="warning" icon={<Calendar className="size-5 text-warning" />} />
        <StatCard label="Cảnh báo cần xem" value={alertEvents} tone="danger" icon={<AlertCircle className="size-5 text-danger" />} />
      </StatRow>

      {/* Tabs */}
      <div className="flex overflow-x-auto border-b border-line text-sm">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`shrink-0 border-b-2 px-3 py-2.5 font-medium transition-colors ${
              tab === t.key
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-ink-muted hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-surface p-3 shadow-card">
        <label className="flex min-h-9 min-w-[280px] flex-1 items-center gap-2 rounded-xl border border-line bg-surface px-3 text-ink-muted focus-within:border-brand-500 lg:max-w-md">
          <Search className="size-4" aria-hidden="true" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm theo khách hàng, mã sự kiện hoặc nội dung..."
            className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
          />
        </label>
        <button
          type="button"
          className="rounded-xl border border-line bg-surface px-3 py-2 text-xs font-medium text-ink-soft hover:bg-surface-muted"
        >
          ⬇ Xuất CSV
        </button>
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(360px,420px)]">
        <div className="min-w-0 overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
          <header className="border-b border-line px-4 py-3">
            <h2 className="text-sm font-semibold text-ink">
              {filtered.length} sự kiện · Sắp xếp mới nhất
            </h2>
          </header>
          <div className="max-h-[560px] overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-surface-muted text-ink-muted border-b border-line">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Thời gian</th>
                  <th className="px-4 py-2.5 font-medium">Người thực hiện</th>
                  <th className="px-4 py-2.5 font-medium">Đối tượng</th>
                  <th className="px-4 py-2.5 font-medium">Hành động</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {filtered.map((e) => {
                  const active = sel?.event_id === e.event_id;
                  const patientName = e.payload?.patient_name ? String(e.payload.patient_name) : null;
                  return (
                    <tr
                      key={e.event_id}
                      onClick={() => setSelId(e.event_id)}
                      className={`cursor-pointer transition-colors ${active ? "bg-brand-50" : "hover:bg-surface-muted"}`}
                    >
                      <td className="px-4 py-3 font-mono text-ink-muted">{fmtTime(e.occurred_at)}</td>
                      <td className="px-4 py-3 font-medium text-ink">{String(e.payload?.staff_name ?? e.source ?? "Hệ thống")}</td>
                      <td className="px-4 py-3 text-ink-soft">{patientName ?? `${e.aggregate_type} · ${e.aggregate_id.slice(0, 8)}`}</td>
                      <td className="px-4 py-3"><span className="font-medium text-brand-700">{eventLabel(e.event_type)}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {sel ? (
          <aside className="w-full shrink-0 space-y-4 rounded-2xl border border-line bg-surface p-4 shadow-card">
            <div className="flex items-start justify-between border-b border-line pb-3">
              <div>
                <span className="inline-block rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-medium text-brand-700">
                  {sel.aggregate_type === "appointment" ? "Lịch hẹn" : sel.aggregate_type === "patient" ? "Khách hàng" : sel.aggregate_type}
                </span>
                <h3 className="mt-1 text-base font-semibold text-ink">{eventLabel(sel.event_type)}</h3>
                <p className="text-xs font-mono text-ink-muted">EV-{sel.event_id.slice(0, 12)}</p>
              </div>
            </div>

            <dl className="space-y-2 text-xs">
              <div className="flex justify-between">
                <dt className="text-ink-muted">Người thực hiện</dt>
                <dd className="font-medium text-ink">{String(sel.payload?.staff_name ?? sel.source ?? "Hệ thống")}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-muted">Thời gian</dt>
                <dd className="font-mono text-ink">{fmtTime(sel.occurred_at)} · {fmtDate(sel.occurred_at)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-muted">Đối tượng</dt>
                <dd className="font-mono text-ink">{sel.payload?.patient_name ? String(sel.payload.patient_name) : sel.aggregate_id.slice(0, 12)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-muted">Nguồn thao tác</dt>
                <dd className="text-ink">{sel.source}</dd>
              </div>
            </dl>

            <div className="space-y-1.5 border-t border-line pt-3">
              <h4 className="text-xs font-semibold text-ink">Dữ liệu thay đổi</h4>
              {changes.length > 0 ? (
                <div className="rounded-xl border border-line overflow-hidden text-xs">
                  <table className="w-full text-left">
                    <thead className="bg-surface-muted text-ink-muted border-b border-line text-[11px]">
                      <tr>
                        <th className="p-2">Trường dữ liệu</th>
                        <th className="p-2">Trước</th>
                        <th className="p-2">Sau</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line text-[11px]">
                      {changes.map((c, i) => (
                        <tr key={i}>
                          <td className="p-2 text-ink-muted">{FIELD_LABELS[c.field] ?? c.field}</td>
                          <td className="p-2 text-amber-600">{c.before}</td>
                          <td className="p-2 font-medium text-success">{c.after}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-ink-muted rounded-xl border border-dashed border-line p-3">
                  Không có dữ liệu thay đổi chi tiết cho sự kiện này.
                </p>
              )}
            </div>

            {sel.payload?.context ? (
              <div className="rounded-xl border border-line p-3 text-xs">
                <h4 className="font-semibold text-ink mb-1">Ngữ cảnh</h4>
                <p className="text-ink-soft">{String(sel.payload.context)}</p>
              </div>
            ) : null}

            <div className="flex items-center gap-2 pt-2 border-t border-line">
              <button
                type="button"
                onClick={() => navigator.clipboard?.writeText(sel.event_id)}
                className="flex-1 inline-flex items-center justify-center gap-1 rounded-xl border border-line bg-surface py-2 text-xs font-medium text-ink-soft hover:bg-surface-muted"
              >
                <Copy size={13} /> Sao chép mã sự kiện
              </button>
              <button
                type="button"
                className="flex-1 inline-flex items-center justify-center gap-1 rounded-xl bg-brand-600 py-2 text-xs font-medium text-white shadow-sm hover:bg-brand-700"
              >
                <ExternalLink size={13} /> Xem sự kiện liên quan
              </button>
            </div>
          </aside>
        ) : null}
      </div>
    </div>
  );
}