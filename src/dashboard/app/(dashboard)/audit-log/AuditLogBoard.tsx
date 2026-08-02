"use client";

// AuditLogBoard — Lịch sử thao tác (image_3).
// Timeline event_log gom theo ngày, kèm filter loại + tìm kiếm.

import { useMemo, useState } from "react";

interface AuditEvent {
  event_id: string;
  event_type: string;
  aggregate_type: string;
  aggregate_id: string;
  payload: Record<string, unknown> | null;
  source: string;
  occurred_at: string;
  actor_staff_id: string | null;
  actor: { full_name: string } | null;
}

// Ba trạng thái khác nhau, không được gộp: có người và đọc được tên; máy sinh
// (relay, worker, Zalo, khách vãng lai) nên không có ai; và có người nhưng RLS
// không cho đọc tên — nói "Hệ thống" ở ca thứ ba là ghi sai lịch sử.
const actorLabel = (e: AuditEvent) => {
  if (e.actor?.full_name) return e.actor.full_name;
  if (e.actor_staff_id) return "Không đọc được tên";
  return "Hệ thống";
};

interface Props {
  events: AuditEvent[];
}

const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Asia/Ho_Chi_Minh",
  });

export default function AuditLogBoard({ events }: Props) {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [actorFilter, setActorFilter] = useState<string>("all");

  const types = useMemo(
    () => [...new Set(events.map((e) => e.event_type))].sort(),
    [events],
  );

  const actors = useMemo(
    () => [...new Set(events.map(actorLabel))].sort((a, b) => a.localeCompare(b, "vi")),
    [events],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return events.filter((e) => {
      if (typeFilter !== "all" && e.event_type !== typeFilter) return false;
      if (actorFilter !== "all" && actorLabel(e) !== actorFilter) return false;
      if (!q) return true;
      return (
        e.event_type.toLowerCase().includes(q) ||
        e.aggregate_type.toLowerCase().includes(q) ||
        e.source.toLowerCase().includes(q) ||
        actorLabel(e).toLowerCase().includes(q) ||
        JSON.stringify(e.payload ?? {}).toLowerCase().includes(q)
      );
    });
  }, [events, search, typeFilter, actorFilter]);

  // Gom theo ngày
  const byDay = useMemo(() => {
    const map = new Map<string, AuditEvent[]>();
    for (const e of filtered) {
      const day = fmtDate(e.occurred_at);
      const list = map.get(day) ?? [];
      list.push(e);
      map.set(day, list);
    }
    return [...map.entries()];
  }, [filtered]);

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <div>
          <h2 className="text-sm font-semibold text-ink">Lịch sử thao tác</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            {events.length} sự kiện · {filtered.length} hiển thị
          </p>
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="ml-auto rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-sm text-ink outline-none"
        >
          <option value="all">Tất cả loại</option>
          {types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          value={actorFilter}
          onChange={(e) => setActorFilter(e.target.value)}
          className="rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-sm text-ink outline-none"
        >
          <option value="all">Tất cả người thao tác</option>
          {actors.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Tìm sự kiện…"
          className="w-56 rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-sm text-ink outline-none focus:border-brand-500"
        />
      </div>

      <div className="flex-1 overflow-y-auto space-y-4">
        {byDay.length === 0 ? (
          <p className="py-10 text-center text-sm text-ink-muted">
            Không có sự kiện nào.
          </p>
        ) : (
          byDay.map(([day, list]) => (
            <section key={day}>
              <h3 className="sticky top-0 z-10 bg-surface-muted px-2 py-1 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                {day}
              </h3>
              <div className="mt-1 space-y-1">
                {list.map((e) => (
                  <div
                    key={e.event_id}
                    className="flex items-start gap-3 rounded-control border border-line bg-surface px-3 py-2"
                  >
                    <span className="mt-1 shrink-0 text-xs tabular-nums text-ink-faint">
                      {fmtTime(e.occurred_at)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                          {e.event_type}
                        </span>
                        <span
                          className={`text-xs font-medium ${
                            e.actor?.full_name ? "text-ink" : "text-ink-faint"
                          }`}
                        >
                          {actorLabel(e)}
                        </span>
                        <span className="text-xs text-ink-muted">
                          {e.aggregate_type} · {e.source}
                        </span>
                      </div>
                      {e.payload && Object.keys(e.payload).length > 0 && (
                        <pre className="mt-1 truncate text-xs text-ink-soft">
                          {JSON.stringify(e.payload)}
                        </pre>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))
        )}
      </div>
    </div>
  );
}