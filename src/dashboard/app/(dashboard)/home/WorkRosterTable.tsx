// Bảng "Lịch làm việc" chỉ-đọc — y hệt file Excel của PK Kim Ngưu.
//
// Khung ở ../RosterGrid. Tệp này chỉ trả lời cho từng ô: đóng hay mở, ai đứng.
// Dữ liệu thật từ `work_roster` (người) và `vi_tri_dong_ca` (ô đen, khối NGHỈ).

import {
  cotCuaTuan,
  weekStartOf,
  type CotLich,
  type Station,
} from "../../../lib/roster";
import {
  RosterGridHead,
  RosterViTriRows,
  nenO,
  type ThongTinO,
} from "../RosterGrid";

export interface RosterRow {
  work_date: string;
  station: string;
  staff_id?: string | null;
  staff_name: string | null;
  shift: string;
}

export interface DongCaRow {
  work_date: string;
  shift: string;
  station: string;
  ly_do: "DONG" | "NGHI";
}

const khoaO = (station: string, date: string, shift: string) =>
  `${station}|${date}|${shift}`;

/** Ai đứng ô nào. Người trực CẢ NGÀY hiện ở mọi ca của ngày ấy — không thì họ
 *  biến khỏi bảng chỉ vì bảng có cột theo ca còn họ không khai ca nào. */
export function gomNguoi(rows: RosterRow[], cot: CotLich[]) {
  const o = new Map<string, string[]>();
  for (const r of rows) {
    if (!r.staff_name) continue;
    const cas =
      r.shift === "FULL"
        ? cot.filter((c) => c.date === r.work_date).map((c) => c.shift)
        : [r.shift];
    for (const ca of cas) {
      const k = khoaO(r.station, r.work_date, ca);
      const ds = o.get(k) ?? [];
      if (!ds.includes(r.staff_name)) ds.push(r.staff_name);
      o.set(k, ds);
    }
  }
  return o;
}

export function gomDong(dong: DongCaRow[]) {
  return new Map(dong.map((d) => [khoaO(d.station, d.work_date, d.shift), d.ly_do]));
}

export default function WorkRosterTable({
  stations,
  dates,
  rows,
  dong = [],
}: {
  /** Danh mục vị trí từ database — xem `viTriTuDb`. */
  stations: readonly Station[];
  dates: string[];
  rows: RosterRow[];
  dong?: DongCaRow[];
}) {
  const weekStart = weekStartOf(dates[0] ?? "") ?? dates[0] ?? "";
  const cot = cotCuaTuan(weekStart, rows);
  const nguoi = gomNguoi(rows, cot);
  const dongO = gomDong(dong);

  const thongTin = (s: Station, c: CotLich): ThongTinO => {
    const k = khoaO(s.key, c.date, c.shift);
    return {
      dong: dongO.get(k) ?? null,
      khoa: [...(nguoi.get(k) ?? [])].sort().join("|"),
    };
  };

  return (
    <div className="max-h-[88vh] min-h-45 max-w-full overflow-auto rounded-card border border-line bg-surface shadow-card">
      <table className="w-full min-w-max border-collapse text-xs">
        <RosterGridHead cot={cot} minWidth={104} />
        <tbody>
          <RosterViTriRows
            stations={stations}
            cot={cot}
            thongTin={thongTin}
            veO={(s, c, rs) => {
              const ten = nguoi.get(khoaO(s.key, c.date, c.shift)) ?? [];
              return (
                <td
                  rowSpan={rs}
                  className={`border border-line-strong ${nenO(s)} px-2 py-1 text-center align-middle text-ink`}
                >
                  {ten.map((n, i) => (
                    <span key={i} className="block whitespace-nowrap leading-snug">
                      {n}
                    </span>
                  ))}
                </td>
              );
            }}
          />
        </tbody>
      </table>
    </div>
  );
}
