// Khung chung của BA bảng "Lịch làm việc": trang chủ (chỉ đọc), lịch chính thức
// (chỉ đọc), và bảng xếp ca của quản lý.
//
// Y HỆT FILE EXCEL xếp lịch của PK Kim Ngưu (Tuyền 16/09/2026: "bảng nó phải
// dạng y hệt như này"):
//
//   • ba cột trái Tầng · Phòng · Vị trí nhân sự
//   • ba hàng đầu  Thứ · ngày · ca     (T2→T6 một ca Tối; T7, CN ba ca)
//   • nền theo PHÒNG, đúng mã màu Excel
//   • ô ĐEN      = vị trí không làm ca ấy   (khác ô trống = cần người, chưa xếp)
//   • khối NGHỈ  = các hàng liền nhau cùng nghỉ ca ấy
//   • ô GỘP DỌC  = một người đứng hai vị trí liền nhau (Lễ tân + Thu ngân…)
//
// CỘT TẦNG TRỞ LẠI (01/10/2026, bảng lịch tuần 28/09 Tuyền gửi: Tầng → Phòng →
// Vị trí). 27/09 đã bỏ cột này vì "bố cục phòng thay đổi liên tục" — lần này tầng
// và tên phòng đều lấy từ PHÒNG THẬT (máy chủ trả `clinic_room.floor` / `.name`
// theo room_id), nên đổi bố cục ở Cấu trúc phòng khám là bảng đổi theo. KHÔNG
// dựng lại cái LỌC cũ: vị trí không tầng (Trưởng ca, `VT-*` thêm ở Dây nối) vẫn
// có hàng, ô Tầng để "—". Không vạch ngăn tầng (ô Tầng gộp đã đủ phân nhóm).
//
// GỘP DỌC SUY RA TỪ DỮ LIỆU, không khai tay (`tinhGopDoc` ở lib/roster): hai vị
// trí LIỀN NHAU có CÙNG người → một ô. Không cần danh sách cặp; ngày phòng khám
// gộp một cặp mới, bảng tự gộp theo.

import { Fragment, type ReactNode } from "react";
import {
  SHIFT_LABEL,
  dayShort,
  fmtDayMonth,
  mauPhong,
  phanTang,
  tinhGopDoc,
  type CotLich,
  type Station,
  type ThongTinO,
} from "../../lib/roster";

export type { ThongTinO, TrangThaiO } from "../../lib/roster";

export const O_TREN = "border-b border-r border-hairline";

const THU_DAY_DU: Record<string, string> = {
  T2: "Thứ Hai",
  T3: "Thứ Ba",
  T4: "Thứ Tư",
  T5: "Thứ Năm",
  T6: "Thứ Sáu",
  T7: "Thứ Bảy",
  CN: "Chủ nhật",
};

/** Ba cột trái. Số cột — cho `colSpan` của hàng nằm ngoài lưới vị trí. */
export const SO_COT_TRAI = 3;

/** Ba cột trái khi cuộn ngang.
 *
 *  Cột TẦNG không dính (hẹp, và cuộn sang phải thì tầng đã rõ theo phòng) — nó
 *  trôi đi trước, rồi cột Phòng dính ở mép trái. Ở 375px, Phòng + Vị trí dính
 *  cộng lại là cả màn — cuộn ngang không thấy được một ô ca nào. Nên dưới `sm`
 *  chỉ cột VỊ TRÍ dính (cột định danh, DESIGN.md §7) và hẹp lại; Tầng và Phòng
 *  trôi theo bảng. Từ `sm` Phòng + Vị trí dính, cạnh nhau (left-40 = đúng bề
 *  rộng cột Phòng). */
const COT_TRAI = [
  "w-14 min-w-14 sm:w-16 sm:min-w-16",
  "w-24 min-w-24 sm:sticky sm:left-0 sm:z-10 sm:w-40 sm:min-w-40",
  "sticky left-0 z-10 w-32 min-w-32 sm:left-40 sm:w-56 sm:min-w-56",
];
/** Cùng ba cột ở tiêu đề — nằm TRÊN ô thân khi cùng dính. */
const COT_TRAI_TIEU_DE = [
  "w-14 min-w-14 sm:w-16 sm:min-w-16",
  "w-24 min-w-24 sm:sticky sm:left-0 sm:z-20 sm:w-40 sm:min-w-40",
  "sticky left-0 z-20 w-32 min-w-32 sm:left-40 sm:w-56 sm:min-w-56",
];
const KE = "border border-line-strong";

/** Ba hàng tiêu đề: Thứ (gộp theo số ca) · ngày (gộp) · ca. */
export function RosterGridHead({
  cot,
  minWidth = 104,
}: {
  cot: CotLich[];
  minWidth?: number;
}) {
  return (
    <thead>
      <tr className="bg-surface-muted">
        {["Tầng", "Phòng", "Vị trí nhân sự"].map((t, i) => (
          <th
            key={t}
            rowSpan={3}
            className={`${COT_TRAI_TIEU_DE[i]} ${KE} bg-surface-muted px-2 py-2 text-center align-middle font-semibold text-ink`}
          >
            {t}
          </th>
        ))}
        {cot.map((c) =>
          c.dauNgay ? (
            <th
              key={`${c.date}-thu`}
              colSpan={c.soCotNgay}
              className={`${KE} px-2 py-1 text-center font-semibold text-ink`}
            >
              {THU_DAY_DU[dayShort(c.date)] ?? dayShort(c.date)}
            </th>
          ) : null,
        )}
      </tr>
      <tr className="bg-surface-muted">
        {cot.map((c) =>
          c.dauNgay ? (
            <th
              key={`${c.date}-ngay`}
              colSpan={c.soCotNgay}
              className={`${KE} px-2 py-1 text-center font-normal text-ink`}
            >
              {fmtDayMonth(c.date)}/{c.date.slice(0, 4)}
            </th>
          ) : null,
        )}
      </tr>
      <tr className="bg-surface-muted">
        {cot.map((c) => (
          <th
            key={`${c.date}-${c.shift}`}
            className={`${KE} px-2 py-1 text-center font-normal text-ink`}
            style={{ minWidth }}
          >
            {SHIFT_LABEL[c.shift]}
          </th>
        ))}
      </tr>
    </thead>
  );
}

/** Thân bảng: mỗi vị trí một hàng, gộp Tầng + Phòng, NGHỈ, gộp dọc.
 *
 *  `thongTin(vị trí, cột)` nói ô ấy đóng hay mở và ai đứng (khoá để gộp).
 *  `veO(vị trí, cột, rowSpan)` vẽ nội dung một ô MỞ — trả về đúng một `<td>`. */
export function RosterViTriRows({
  stations,
  cot,
  thongTin,
  veO,
}: {
  /** Danh mục vị trí từ database (`viTriTuDb`), theo thứ tự dòng Excel. MỌI
   *  vị trí có hàng — kể cả vị trí không gắn phòng / không tầng (Trưởng ca). */
  stations: readonly Station[];
  cot: CotLich[];
  thongTin: (station: Station, c: CotLich) => ThongTinO;
  veO: (station: Station, c: CotLich, rowSpan: number) => ReactNode;
}) {
  const cacTang = phanTang(stations);
  // Mỗi hàng biết nó có mở ô Tầng / ô Phòng không (hàng đầu nhóm) và rowSpan.
  const hang = cacTang.flatMap((t) =>
    t.phongs.flatMap((p, pi) =>
      p.stations.map((s, si) => ({
        s,
        tang: pi === 0 && si === 0 ? t : null,
        phong: si === 0 ? p : null,
        mau: mauPhong(p.maPhong),
      })),
    ),
  );
  const o = hang.map((h) => cot.map((c) => thongTin(h.s, c)));
  // `span[i][ci]` = rowSpan của ô ở hàng i (0 = ô này đã gộp vào ô trên).
  const span = tinhGopDoc(o);

  return (
    <>
      {hang.map((h, i) => (
        <tr key={h.s.key} className="align-middle">
          {h.tang ? (
            <td
              rowSpan={h.tang.soViTri}
              className={`${COT_TRAI[0]} ${KE} bg-surface px-2 py-2 text-center font-semibold text-ink`}
            >
              {h.tang.tang || <span className="font-normal text-ink-faint">—</span>}
            </td>
          ) : null}
          {h.phong ? (
            <td
              rowSpan={h.phong.stations.length}
              className={`${COT_TRAI[1]} ${KE} ${h.mau} px-2 py-2 font-semibold text-ink`}
            >
              {h.phong.phong || <span className="font-normal text-ink-faint">—</span>}
            </td>
          ) : null}
          <td className={`${COT_TRAI[2]} ${KE} ${h.mau} px-2 py-1 text-ink`} title={h.s.label}>
            {h.s.short}
          </td>
          {cot.map((c, ci) => {
            const rs = span[i][ci];
            if (rs === 0) return null;
            const k = `${h.s.key}-${c.date}-${c.shift}`;
            const tt = o[i][ci];
            if (tt.dong === "NGHI") {
              return (
                <td
                  key={k}
                  rowSpan={rs}
                  aria-label="Nghỉ"
                  className={`${KE} bg-lich-nghi text-center align-middle text-emph font-bold text-warning-bg`}
                >
                  {rs > 1 ? "NGHỈ" : null}
                </td>
              );
            }
            // Ô ĐÓNG (DONG) không còn chặn (28/09/2026): vẽ như ô thường, có
            // nút + để xếp người. Chỉ khối NGHỈ còn đặc biệt.
            return <Fragment key={k}>{veO(h.s, c, rs)}</Fragment>;
          })}
        </tr>
      ))}
    </>
  );
}

/** Nền của một ô MỞ: màu phòng của vị trí ấy (khoá theo mã phòng), như Excel. */
export function nenO(station: Station): string {
  return mauPhong(station.maPhong);
}
