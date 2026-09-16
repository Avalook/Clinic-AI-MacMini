// Bảng "Lịch làm việc" trên trang chủ — chỉ đọc.
//
// Form Y HỆT file Excel của PK Kim Ngưu: hàng = Tầng → Phòng → Vị trí, cột =
// ngày × ca (T2→T6 một ca Tối; T7, CN ba ca). Ô = người đứng chỗ ấy ca ấy.
// Dữ liệu thật từ `work_roster` (server fetch ở home/page.tsx). Khung dùng
// chung với hai bảng kia: ../RosterGrid.

import {
  cotCuaTuan,
  demBacSiTruc,
  weekStartOf,
  type Shift,
} from "../../../lib/roster";
import {
  RosterGridHead,
  RosterViTriRows,
  RosterLichKhamRows,
  O_TREN,
} from "../RosterGrid";

export interface RosterRow {
  work_date: string;
  station: string;
  staff_id?: string | null;
  staff_name: string | null;
  shift: string;
}

/** Khoá một ô: vị trí + ngày + ca. */
function khoaO(station: string, date: string, shift: string): string {
  return `${station}|${date}|${shift}`;
}

export default function WorkRosterTable({
  dates,
  rows,
}: {
  dates: string[];
  rows: RosterRow[];
}) {
  const weekStart = weekStartOf(dates[0] ?? "") ?? dates[0] ?? "";
  const cot = cotCuaTuan(weekStart, rows);

  // Một ô có thể có nhiều người — Excel cũng viết hai tên chung một ô khi hôm
  // ấy cần hai người. Gom hết, không cắt bớt: cắt là bảng nói dối về ai trực.
  const o = new Map<string, string[]>();
  for (const r of rows) {
    if (!r.staff_name) continue;
    // Người trực CẢ NGÀY hiện ở mọi ca của ngày ấy, nếu không họ biến mất khỏi
    // bảng chỉ vì bảng có cột theo ca còn họ thì không khai ca nào.
    const cas: string[] =
      r.shift === "FULL"
        ? cot.filter((c) => c.date === r.work_date).map((c) => c.shift)
        : [r.shift];
    for (const ca of cas) {
      const k = khoaO(r.station, r.work_date, ca);
      o.set(k, [...(o.get(k) ?? []), r.staff_name]);
    }
  }

  const veO = (stationKey: string, date: string, shift: Shift, dauNgay: boolean) => {
    const ten = o.get(khoaO(stationKey, date, shift)) ?? [];
    return (
      <td
        className={`${O_TREN} px-2 py-1.5 text-center text-ink ${
          dauNgay ? "border-l border-l-line" : ""
        }`}
      >
        {ten.length === 0 ? (
          <span className="text-ink-faint">—</span>
        ) : (
          ten.map((n, i) => (
            <span key={i} className="block whitespace-nowrap leading-snug">
              {n}
            </span>
          ))
        )}
      </td>
    );
  };

  return (
    <div className="max-h-[88vh] min-h-45 max-w-full overflow-auto rounded-card border border-line bg-surface shadow-card">
      <table className="w-full min-w-max border-collapse text-xs">
        <RosterGridHead cot={cot} minWidth={104} />
        <tbody>
          <RosterLichKhamRows
            cot={cot}
            demBacSi={(c) => demBacSiTruc(rows, c.date, c.shift)}
            oCua={(s, c) => veO(s.key, c.date, c.shift, c.dauNgay)}
          />
          <RosterViTriRows
            cot={cot}
            oCua={(s, c) => veO(s.key, c.date, c.shift, c.dauNgay)}
          />
        </tbody>
      </table>
    </div>
  );
}
