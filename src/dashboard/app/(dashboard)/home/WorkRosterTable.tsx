// Bảng "Lịch làm việc" — form Y HỆT file Excel "BẢNG LÀM VIỆC" (sheet LLV):
// hàng = NGÀY (T2..CN tuần này), MỖI NGÀY HAI HÀNG CON (mỗi hàng một người);
// cột = TRẠM, GOM THEO TẦNG ở hàng header trên, kèm cột "Số BS" ngay sau Lịch
// khám. Ô = nhân viên trực (+ ca nếu nửa buổi). Read-only, data thật từ
// work_roster (server fetch ở home/page.tsx). Header dùng chung: ../RosterGrid.

import {
  chiaHaiHang,
  demBacSiTruc,
  dayShort,
  fmtDayMonth,
  SHIFT_LABEL,
  type Shift,
} from "../../../lib/roster";
import { RosterGridHead, RosterDayRows, O_TREN, O_DUOI } from "../RosterGrid";

export interface RosterRow {
  work_date: string;
  station: string;
  staff_id?: string | null;
  staff_name: string | null;
  shift: string;
}

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
    <div className="max-h-[88vh] min-h-45 max-w-full overflow-auto rounded-card border border-line bg-surface shadow-card">
      <table className="w-full min-w-max border-collapse text-xs">
        <RosterGridHead minWidth={92} />
        <tbody>
          {dates.map((d, ri) => {
            const dm = byDate.get(d);
            return (
              <RosterDayRows
                key={d}
                nhan={`${dayShort(d)} · ${fmtDayMonth(d)}`}
                soBacSi={demBacSiTruc(rows, d)}
                vach={ri % 2 ? "bg-brand-50" : "bg-white"}
                oCua={(s, hang) => {
                  const names = chiaHaiHang(dm?.get(s.key) ?? [])[hang];
                  const isDoctor = s.key === "LICH_KHAM";
                  return (
                    <td
                      className={
                        (hang === 0 ? O_TREN : O_DUOI) +
                        " px-2 py-1.5 text-center " +
                        (isDoctor ? "font-semibold text-brand-700" : "text-ink")
                      }
                    >
                      {names.length === 0 ? (
                        // Chỉ hàng TRÊN mới vẽ gạch "trống"; hàng dưới để trắng,
                        // nếu không mỗi ngày trống hiện ra hai gạch chồng nhau.
                        hang === 0 ? (
                          <span className="text-ink-faint">—</span>
                        ) : null
                      ) : (
                        names.map((n, i) => (
                          <span key={i} className="block whitespace-nowrap leading-snug">
                            {n}
                          </span>
                        ))
                      )}
                    </td>
                  );
                }}
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
