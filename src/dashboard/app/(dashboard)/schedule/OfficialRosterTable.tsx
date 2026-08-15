// Lịch làm việc chính thức (chỉ đọc) — CÙNG form với bảng trang chủ và bảng xếp
// ca bên dưới: ngày × trạm, gom theo tầng, mỗi ngày HAI HÀNG CON, cột "Số BS"
// ngay sau Lịch khám. Header + khung hàng dùng chung ở ../RosterGrid.

import {
  SHIFT_LABEL,
  chiaHaiHang,
  demBacSiTruc,
  dayShort,
  fmtDayMonth,
  type Shift,
} from "../../../lib/roster";
import { RosterGridHead, RosterDayRows, O_TREN, O_DUOI } from "../RosterGrid";

export interface OfficialRosterRow {
  work_date: string;
  station: string;
  staff_id?: string | null;
  staff_name: string | null;
  shift: string;
}

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
        <RosterGridHead minWidth={92} />
        <tbody>
          {dates.map((date, index) => (
            <RosterDayRows
              key={date}
              nhan={`${dayShort(date)} · ${fmtDayMonth(date)}`}
              soBacSi={demBacSiTruc(rows, date)}
              vach={index % 2 === 0 ? "bg-surface" : "bg-surface-muted"}
              oCua={(station, hang) => {
                const assignments = chiaHaiHang(
                  rows.filter(
                    (row) =>
                      row.work_date === date &&
                      row.station === station.key &&
                      row.staff_name,
                  ),
                )[hang];
                return (
                  <td
                    className={
                      (hang === 0 ? O_TREN : O_DUOI) +
                      " px-2 py-1.5 text-center text-ink"
                    }
                  >
                    {assignments.length === 0 ? (
                      hang === 0 ? <span className="text-ink-faint">—</span> : null
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
              }}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
