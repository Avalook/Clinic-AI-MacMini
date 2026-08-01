"use client";

// Lịch làm việc dạng KANBAN theo tuần: 7 cột = 7 ngày (T2→CN). Mỗi thẻ là một
// phân công; hover = nổi lên, click = mở chi tiết (trạm đầy đủ + ca + người).
// Dùng cho mọi vai trò: cá nhân thấy thẻ của mình, quản lý thấy tất cả.

import { useState } from "react";
import {
  STATION_SHORT,
  STATION_LABEL,
  STATION_GROUP,
  GROUP_COLOR,
  SHIFT_LABEL,
  dayShort,
  dayLabel,
  fmtDayMonth,
  type Shift,
} from "../../../lib/roster";

export interface KanbanRosterRow {
  id: string;
  work_date: string;
  shift: Shift;
  station: string;
  staff_id: string | null;
  staff_name: string;
}

export default function WeekKanban({
  dates,
  rows,
  todayIso,
  personal,
}: {
  dates: string[];
  rows: KanbanRosterRow[];
  todayIso: string;
  /** true: nhấn mạnh TRẠM (xem lịch của mình); false: nhấn mạnh NGƯỜI (quản lý). */
  personal: boolean;
}) {
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <div className="flex gap-3 overflow-x-auto pb-2 [scrollbar-width:thin] lg:grid lg:grid-cols-7 lg:gap-2 lg:overflow-visible">
      {dates.map((d) => {
        const items = rows.filter((r) => r.work_date === d);
        const isToday = d === todayIso;
        return (
          <div
            key={d}
            className="flex min-w-[80%] shrink-0 snap-start flex-col sm:min-w-[44%] lg:min-w-0"
          >
            {/* Đầu cột */}
            <div
              className={
                "mb-2 rounded-lg px-3 py-2 text-center " +
                (isToday
                  ? "bg-brand-600 text-surface"
                  : "bg-brand-100 text-brand-800")
              }
            >
              <div className="text-xs font-semibold uppercase tracking-wide">
                {dayShort(d)}
              </div>
              <div className={isToday ? "text-sm" : "text-sm text-ink"}>
                {fmtDayMonth(d)}
              </div>
            </div>

            {/* Thẻ */}
            <div className="space-y-1.5">
              {items.length === 0 && (
                <p className="rounded-control border border-dashed border-line py-4 text-center text-[11px] text-ink-faint">
                  —
                </p>
              )}
              {items.map((it) => {
                const group = STATION_GROUP[it.station] ?? "";
                const color = GROUP_COLOR[group] ?? "var(--color-ink-muted)";
                const open = openId === it.id;
                const primary = personal
                  ? STATION_SHORT[it.station] ?? it.station
                  : it.staff_name;
                const secondary = personal
                  ? SHIFT_LABEL[it.shift]
                  : STATION_SHORT[it.station] ?? it.station;
                return (
                  <button
                    key={it.id}
                    onClick={() => setOpenId(open ? null : it.id)}
                    style={{ borderLeftColor: color }}
                    className={
                      "w-full rounded-control border border-l-4 border-line bg-surface p-2 text-left shadow-card transition-all duration-150 hover:-translate-y-0.5 hover:shadow-panel " +
                      (open ? "ring-2 ring-brand-600/30" : "")
                    }
                  >
                    <div className="flex items-center gap-1.5">
                      <span
                        className="h-2 w-2 shrink-0 rounded-full"
                        style={{ backgroundColor: color }}
                      />
                      <span className="truncate text-sm font-medium text-ink">
                        {primary}
                      </span>
                    </div>
                    <p className="mt-0.5 truncate pl-3.5 text-xs text-ink-muted">
                      {secondary}
                      {!personal && it.shift !== "FULL"
                        ? ` · ${SHIFT_LABEL[it.shift]}`
                        : ""}
                    </p>

                    {/* Chi tiết khi click */}
                    {open && (
                      <div className="mt-2 space-y-1 border-t border-surface-sunken pt-2 text-xs text-ink-soft">
                        <p>
                          <span className="text-ink-faint">Vị trí: </span>
                          {STATION_LABEL[it.station] ?? it.station}
                        </p>
                        <p>
                          <span className="text-ink-faint">Ca: </span>
                          {SHIFT_LABEL[it.shift]}
                        </p>
                        <p>
                          <span className="text-ink-faint">Người: </span>
                          {it.staff_name}
                        </p>
                        <p>
                          <span className="text-ink-faint">Ngày: </span>
                          {dayLabel(it.work_date)} · {fmtDayMonth(it.work_date)}
                        </p>
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
