// Khung chung của BA bảng "Lịch làm việc": trang chủ (chỉ đọc), lịch chính thức
// (chỉ đọc), và bảng xếp ca của quản lý.
//
// Y HỆT FILE EXCEL xếp lịch của PK Kim Ngưu (Tuyền 16/09/2026: "bảng nó phải
// dạng y hệt như này"):
//
//   • hai cột trái Phòng · Vị trí nhân sự
//   • ba hàng đầu  Thứ · ngày · ca     (T2→T6 một ca Tối; T7, CN ba ca)
//   • nền theo PHÒNG, đúng mã màu Excel
//   • ô ĐEN      = vị trí không làm ca ấy   (khác ô trống = cần người, chưa xếp)
//   • khối NGHỈ  = các hàng liền nhau cùng nghỉ ca ấy
//   • ô GỘP DỌC  = một người đứng hai vị trí liền nhau (Lễ tân + Thu ngân…)
//
// BỎ CỘT TẦNG (27/09/2026 đợt 3). Phòng khám: "Bỏ hiển thị tầng 1, 2, 4 ở phần
// Lịch làm việc vì bố cục phòng thay đổi liên tục". Cùng lúc bỏ vạch xanh ngăn
// tầng, và bỏ luôn cái LỌC đi kèm: bản cũ chỉ vẽ vị trí có tầng, nên Trưởng ca
// và mọi vị trí quản lý thêm ở màn Dây nối (không có ô tầng) không có hàng.
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
  phanPhong,
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

/** Hai cột trái. Số cột — cho `colSpan` của hàng nằm ngoài lưới vị trí. */
export const SO_COT_TRAI = 2;

/** Hai cột trái khi cuộn ngang.
 *
 *  Ở 375px, hai cột dính cộng lại (160 + 224 = 384px) là cả màn — cuộn ngang
 *  không thấy được một ô ca nào. Nên dưới `sm` chỉ cột VỊ TRÍ dính (cột định
 *  danh, DESIGN.md §7) và hẹp lại; cột Phòng trôi đi theo bảng. Từ `sm` cả hai
 *  dính, cạnh nhau (left-40 = đúng bề rộng cột Phòng). */
const COT_TRAI = [
  "w-24 min-w-24 sm:sticky sm:left-0 sm:z-10 sm:w-40 sm:min-w-40",
  "sticky left-0 z-10 w-32 min-w-32 sm:left-40 sm:w-56 sm:min-w-56",
];
/** Cùng hai cột ở tiêu đề — nằm TRÊN ô thân khi cả hai cùng dính. */
const COT_TRAI_TIEU_DE = [
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
        {["Phòng", "Vị trí nhân sự"].map((t, i) => (
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

/** Thân bảng: mỗi vị trí một hàng, gộp Phòng, ô đen, NGHỈ, gộp dọc.
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
   *  vị trí có hàng — kể cả vị trí không gắn phòng (Trưởng ca). */
  stations: readonly Station[];
  cot: CotLich[];
  thongTin: (station: Station, c: CotLich) => ThongTinO;
  veO: (station: Station, c: CotLich, rowSpan: number) => ReactNode;
}) {
  const cacPhong = phanPhong(stations);
  const viTri = cacPhong.flatMap((p) => p.stations);
  const o = viTri.map((s) => cot.map((c) => thongTin(s, c)));
  // `span[i][ci]` = rowSpan của ô ở hàng i (0 = ô này đã gộp vào ô trên).
  const span = tinhGopDoc(o);
  // Chỉ số hàng đầu của từng nhóm phòng trong `viTri`.
  const dauNhom = cacPhong.map((_, pi) =>
    cacPhong.slice(0, pi).reduce((n, p) => n + p.stations.length, 0),
  );

  return (
    <>
      {cacPhong.map((phong, pi) => {
        const mau = mauPhong(phong.maPhong);
        return (
          <Fragment key={`${phong.maPhong || phong.phong}-${phong.stations[0].key}`}>
            {phong.stations.map((s, si) => {
              const i = dauNhom[pi] + si;
              return (
                <tr key={s.key} className="align-middle">
                  {si === 0 ? (
                    <td
                      rowSpan={phong.stations.length}
                      className={`${COT_TRAI[0]} ${KE} ${mau} px-2 py-2 font-semibold text-ink`}
                    >
                      {phong.phong || <span className="font-normal text-ink-faint">—</span>}
                    </td>
                  ) : null}
                  <td
                    className={`${COT_TRAI[1]} ${KE} ${mau} px-2 py-1 text-ink`}
                    title={s.label}
                  >
                    {s.short}
                  </td>
                  {cot.map((c, ci) => {
                    const rs = span[i][ci];
                    if (rs === 0) return null;
                    const k = `${s.key}-${c.date}-${c.shift}`;
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
                    return <Fragment key={k}>{veO(s, c, rs)}</Fragment>;
                  })}
                </tr>
              );
            })}
          </Fragment>
        );
      })}
    </>
  );
}

/** Nền của một ô MỞ: màu phòng của vị trí ấy (khoá theo mã phòng), như Excel. */
export function nenO(station: Station): string {
  return mauPhong(station.maPhong);
}
