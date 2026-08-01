import {
  SHIFT_LABEL,
  STATIONS,
  STATION_SEGMENTS,
  dayShort,
  fmtDayMonth,
  type Shift,
} from "../../../lib/roster";

export interface OfficialRosterRow {
  work_date: string;
  station: string;
  staff_name: string | null;
  shift: string;
}

const HEADER_CELL =
  "border-b border-r border-line px-2 py-2 text-center align-middle font-semibold text-brand-800";

export default function OfficialRosterTable({
  dates,
  rows,
}: {
  dates: string[];
  rows: OfficialRosterRow[];
}) {
  return (
    <div className="max-h-[88vh] min-h-[180px] max-w-full overflow-auto rounded-card border border-line bg-surface shadow-card">
      <table className="w-full min-w-max border-collapse text-xs">
        <thead>
          <tr className="bg-brand-100">
            <th
              rowSpan={2}
              className="sticky left-0 z-20 border-b border-r border-line bg-brand-100 px-2 py-2 text-left font-semibold text-brand-800"
            >
              Ngày
            </th>
            {STATION_SEGMENTS.map((segment) =>
              segment.floor === "" ? (
                segment.stations.map((station) => (
                  <th
                    key={station.key}
                    rowSpan={2}
                    className={`min-w-[96px] ${HEADER_CELL}`}
                  >
                    {station.short}
                  </th>
                ))
              ) : (
                <th
                  key={segment.floor}
                  colSpan={segment.stations.length}
                  className={`${HEADER_CELL} border-t-2 border-t-brand-400`}
                >
                  {segment.floor}
                </th>
              ),
            )}
          </tr>
          <tr className="bg-brand-50">
            {STATIONS.filter((station) => station.floor !== "").map((station) => (
              <th
                key={station.key}
                className="min-w-[92px] border-b border-r border-line px-2 py-1.5 text-center font-medium text-brand-700"
              >
                {station.short}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dates.map((date, index) => (
            <tr
              key={date}
              className={index % 2 === 0 ? "bg-surface" : "bg-brand-50"}
            >
              <td className="sticky left-0 z-10 whitespace-nowrap border-b border-r border-line bg-inherit px-2 py-2 font-medium text-ink">
                {dayShort(date)} · {fmtDayMonth(date)}
              </td>
              {STATIONS.map((station) => {
                const assignments = rows.filter(
                  (row) =>
                    row.work_date === date &&
                    row.station === station.key &&
                    row.staff_name,
                );
                return (
                  <td
                    key={station.key}
                    className="border-b border-r border-line px-2 py-2 text-center text-ink"
                  >
                    {assignments.length === 0 ? (
                      <span className="text-ink-faint">—</span>
                    ) : (
                      assignments.map((assignment, assignmentIndex) => {
                        const suffix =
                          assignment.shift && assignment.shift !== "FULL"
                            ? ` · ${SHIFT_LABEL[assignment.shift as Shift] ?? assignment.shift}`
                            : "";
                        return (
                          <span
                            key={`${assignment.staff_name}-${assignmentIndex}`}
                            className="block whitespace-nowrap leading-snug"
                          >
                            {assignment.staff_name}
                            {suffix}
                          </span>
                        );
                      })
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
