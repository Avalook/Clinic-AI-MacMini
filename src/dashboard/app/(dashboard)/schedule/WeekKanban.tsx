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
                  ? "bg-[#ec4899] text-white"
                  : "bg-[#fce7f3] text-[#9d2463]")
              }
            >
              <div className="text-xs font-semibold uppercase tracking-wide">
                {dayShort(d)}
              </div>
              <div className={isToday ? "text-sm" : "text-sm text-[#171717]"}>
                {fmtDayMonth(d)}
              </div>
            </div>

            {/* Thẻ */}
            <div className="space-y-1.5">
              {items.length === 0 && (
                <p className="rounded-lg border border-dashed border-[#e4e4e7] py-4 text-center text-[11px] text-[#c4c4c8]">
                  —
                </p>
              )}
              {items.map((it) => {
                const group = STATION_GROUP[it.station] ?? "";
                const color = GROUP_COLOR[group] ?? "#71717a";
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
                      "w-full rounded-lg border border-l-4 border-[#e4e4e7] bg-white p-2 text-left shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-all duration-150 hover:-translate-y-0.5 hover:shadow-md " +
                      (open ? "ring-2 ring-[#ec4899]/30" : "")
                    }
                  >
                    <div className="flex items-center gap-1.5">
                      <span
                        className="h-2 w-2 shrink-0 rounded-full"
                        style={{ backgroundColor: color }}
                      />
                      <span className="truncate text-sm font-medium text-[#171717]">
                        {primary}
                      </span>
                    </div>
                    <p className="mt-0.5 truncate pl-3.5 text-xs text-[#71717a]">
                      {secondary}
                      {!personal && it.shift !== "FULL"
                        ? ` · ${SHIFT_LABEL[it.shift]}`
                        : ""}
                    </p>

                    {/* Chi tiết khi click */}
                    {open && (
                      <div className="mt-2 space-y-1 border-t border-[#f4f4f5] pt-2 text-xs text-[#4d4d4d]">
                        <p>
                          <span className="text-[#a1a1aa]">Vị trí: </span>
                          {STATION_LABEL[it.station] ?? it.station}
                        </p>
                        <p>
                          <span className="text-[#a1a1aa]">Ca: </span>
                          {SHIFT_LABEL[it.shift]}
                        </p>
                        <p>
                          <span className="text-[#a1a1aa]">Người: </span>
                          {it.staff_name}
                        </p>
                        <p>
                          <span className="text-[#a1a1aa]">Ngày: </span>
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
