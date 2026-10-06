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
import Chip from "../../../components/ui/Chip";
import { vaiKemTen } from "../../../lib/doctor-name";

export interface RosterRow {
  work_date: string;
  station: string;
  staff_id?: string | null;
  staff_name: string | null;
  shift: string;
  /** Vai đầy đủ / ngắn do máy chủ trả (`clinic_membership.role`, 27/09 đợt 3). */
  vai?: string | null;
  vai_ngan?: string | null;
  /** Chỉ ở bảng XEM PHIÊN BẢN (lịch sử lịch trực, 06/10/2026): ô này khác bản
   *  trước thế nào. Bảng thường không có trường này. */
  thay_doi?: LoaiThayDoi | null;
  /** Người đứng ô ở bản trước — khi `thay_doi` = DOI_NGUOI. */
  truoc_ten?: string | null;
}

/** Ba loại khác nhau giữa hai phiên bản lịch trực (máy chủ tính). */
export type LoaiThayDoi = "THEM" | "XOA" | "DOI_NGUOI";

/** Một người trong ô: tên hiển thị + chip vai (rỗng = không in chip). */
export interface NguoiTrongO {
  ten: string;
  vai: string;
  loai?: LoaiThayDoi | null;
  truoc?: string | null;
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
  const o = new Map<string, NguoiTrongO[]>();
  for (const r of rows) {
    if (!r.staff_name) continue;
    const cas =
      r.shift === "FULL"
        ? cot.filter((c) => c.date === r.work_date).map((c) => c.shift)
        : [r.shift];
    for (const ca of cas) {
      const k = khoaO(r.station, r.work_date, ca);
      const ds = o.get(k) ?? [];
      const loai = r.thay_doi ?? null;
      if (!ds.some((n) => n.ten === r.staff_name && (n.loai ?? null) === loai)) {
        ds.push({
          ten: r.staff_name,
          vai: vaiKemTen(r.staff_name, r.vai_ngan),
          loai,
          truoc: r.truoc_ten ?? null,
        });
      }
      o.set(k, ds);
    }
  }
  return o;
}

export function gomDong(dong: DongCaRow[]) {
  return new Map(dong.map((d) => [khoaO(d.station, d.work_date, d.shift), d.ly_do]));
}

/** Nền + chữ của ô / tên khác bản trước — token trạng thái sẵn có (DESIGN.md
 *  §2), cùng họ màu với chip chú thích ở màn lịch sử. Ô có nhiều loại thì loại
 *  nặng nhất quyết nền: xoá > đổi người > thêm. */
export const MAU_THAY_DOI: Record<LoaiThayDoi, { nen: string; chu: string }> = {
  XOA: { nen: "bg-danger-bg", chu: "text-danger line-through" },
  DOI_NGUOI: { nen: "bg-info-bg", chu: "text-info font-semibold" },
  THEM: { nen: "bg-success-bg", chu: "text-success font-semibold" },
};
const THU_TU_NANG: LoaiThayDoi[] = ["XOA", "DOI_NGUOI", "THEM"];
const NHAN_SR: Record<LoaiThayDoi, string> = {
  THEM: "Mới thêm:",
  XOA: "Đã xoá:",
  DOI_NGUOI: "Đổi sang:",
};

export function nenThayDoi(ds: Pick<NguoiTrongO, "loai">[]): string | null {
  const loai = THU_TU_NANG.find((l) => ds.some((n) => n.loai === l));
  return loai ? MAU_THAY_DOI[loai].nen : null;
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
  /** Bảng xem phiên bản truyền thêm dòng ĐÃ XOÁ (`thay_doi` = XOA) — vẽ gạch
   *  ngang tại chỗ cũ. */
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
      // Kèm loại thay đổi: ô đổi không được gộp dọc với ô không đổi.
      khoa: (nguoi.get(k) ?? [])
        .map((n) => `${n.ten}~${n.loai ?? ""}~${n.truoc ?? ""}`)
        .sort()
        .join("|"),
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
                  className={`border border-line-strong ${nenThayDoi(ten) ?? nenO(s)} px-2 py-1 text-center align-middle text-ink`}
                >
                  {ten.map((n, i) => (
                    <span
                      key={i}
                      className="flex items-center justify-center gap-1 whitespace-nowrap leading-snug"
                    >
                      {n.loai === "DOI_NGUOI" && n.truoc ? (
                        <>
                          <span className="text-ink-muted line-through">{n.truoc}</span>
                          <span aria-hidden="true">→</span>
                        </>
                      ) : null}
                      {/* Không chỉ bằng màu: "+" = thêm, gạch ngang = xoá, mũi
                          tên = đổi người. */}
                      {n.loai === "THEM" ? <span aria-hidden="true">+</span> : null}
                      {n.loai ? <span className="sr-only">{NHAN_SR[n.loai]}</span> : null}
                      <span className={n.loai ? MAU_THAY_DOI[n.loai].chu : undefined}>
                        {n.ten}
                      </span>
                      {n.vai && n.loai !== "XOA" ? <Chip>{n.vai}</Chip> : null}
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
