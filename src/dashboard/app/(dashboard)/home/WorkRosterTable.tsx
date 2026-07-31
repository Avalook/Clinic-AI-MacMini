// Bảng "Lịch làm việc" — form Y HỆT file Excel "BẢNG LÀM VIỆC" (sheet LLV):
// hàng = NGÀY (T2..CN tuần này); cột = TRẠM, GOM THEO TẦNG ở hàng header trên
// (Lịch khám · Thủ thuật ngoài giờ · HSS · Tầng 1 · Tầng 2 · Tầng 4 · Tầng 4
// phòng trong). Ô = nhân viên trực (+ ca nếu nửa buổi). Read-only, data thật từ
// work_roster (server fetch ở home/page.tsx). Tông hồng nhẹ, cuộn ngang/dọc.

import {
  STATIONS,
  STATION_SEGMENTS,
  FLOOR_COLOR,
  dayShort,
  fmtDayMonth,
  SHIFT_LABEL,
  type Shift,
} from "../../../lib/roster";

export interface RosterRow {
  work_date: string;
  station: string;
  staff_name: string | null;
  shift: string;
}

const TH_BASE =
  "border-b border-r border-brand-100 px-2 py-2 text-center align-middle font-semibold text-brand-800";

export default function WorkRosterTable({
  dates,
  rows,
}: {
  dates: string[];
  rows: RosterRow[];
}) {
  // byDate[date][station] = danh sách "Tên (· ca)".
  const byDate = new Map<string, Map<string, string[]>>();
  for (const r of rows) {
    if (!r.staff_name) continue;
    const dm = byDate.get(r.work_date) ?? new Map<string, string[]>();
    const list = dm.get(r.station) ?? [];
    const suffix =
      r.shift && r.shift !== "FULL"
        ? ` · ${SHIFT_LABEL[r.shift as Shift] ?? r.shift}`
        : "";
    list.push(r.staff_name + suffix);
    dm.set(r.station, list);
    byDate.set(r.work_date, dm);
  }

  return (
    <div className="overflow-auto rounded-xl border border-brand-100 bg-white shadow-[0_1px_3px_rgba(236,72,153,0.08)] max-h-[88vh] min-h-[180px] max-w-full">
      <table className="w-full min-w-max border-collapse text-xs">
        <thead>
          {/* Hàng 1: TẦNG (gộp cột) */}
          <tr className="bg-brand-100">
            <th
              rowSpan={2}
              className="sticky left-0 z-20 border-b border-r border-brand-100 bg-brand-100 px-2 py-2 text-left font-semibold text-brand-800"
            >
              Ngày
            </th>
            {STATION_SEGMENTS.map((seg) =>
              seg.floor === "" ? (
                seg.stations.map((s) => (
                  <th key={s.key} rowSpan={2} className={`min-w-[96px] ${TH_BASE}`}>
                    {s.short}
                  </th>
                ))
              ) : (
                <th
                  key={seg.floor}
                  colSpan={seg.stations.length}
                  className={`${TH_BASE} border-t-2`}
                  style={{ borderTopColor: FLOOR_COLOR[seg.floor] ?? "#ec4899" }}
                >
                  {seg.floor}
                </th>
              ),
            )}
          </tr>
          {/* Hàng 2: tên TRẠM (các cột thuộc tầng) */}
          <tr className="bg-brand-50">
            {STATIONS.filter((s) => s.floor !== "").map((s) => (
              <th
                key={s.key}
                className="min-w-[92px] border-b border-r border-brand-100 px-2 py-1.5 text-center font-medium text-[#b83280]"
              >
                {s.short}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dates.map((d, ri) => {
            const dm = byDate.get(d);
            return (
              <tr key={d} className={"align-top " + (ri % 2 ? "bg-brand-50" : "bg-white")}>
                <td className="sticky left-0 z-10 whitespace-nowrap border-b border-r border-brand-100 bg-inherit px-2 py-2 font-medium text-ink">
                  {dayShort(d)} · {fmtDayMonth(d)}
                </td>
                {STATIONS.map((s) => {
                  const names = dm?.get(s.key) ?? [];
                  const isDoctor = s.key === "LICH_KHAM";
                  return (
                    <td
                      key={s.key}
                      className={
                        "border-b border-r border-brand-100 px-2 py-2 text-center " +
                        (isDoctor
                          ? "font-semibold text-[#b83280]"
                          : "text-ink")
                      }
                    >
                      {names.length === 0 ? (
                        <span className="text-[#e0b9cd]">—</span>
                      ) : (
                        names.map((n, i) => (
                          <span key={i} className="block whitespace-nowrap leading-snug">
                            {n}
                          </span>
                        ))
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
