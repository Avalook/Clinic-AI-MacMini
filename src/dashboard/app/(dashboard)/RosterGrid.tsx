// Khung chung của BA bảng "Lịch làm việc": trang chủ (chỉ đọc), lịch chính thức
// (chỉ đọc), và bảng xếp ca của quản lý.
//
// ĐÃ LẬT CHIỀU 16/09/2026, theo đúng file Excel của PK Kim Ngưu:
//
//        TRƯỚC                          NAY (= Excel)
//   hàng = ngày                    hàng = Tầng → Phòng → Vị trí
//   cột  = trạm                    cột  = ngày × ca
//
// Vì sao phải lật, chứ không chỉ đổi danh sách trạm: Kim Ngưu có 27 vị trí.
// Giữ chiều cũ là một bảng 27 cột — cuộn ngang ba màn hình mới đọc hết một
// ngày. Còn chiều mới ra đúng 11 cột (T2→T6 mỗi ngày một ca Tối; T7, CN mỗi
// ngày ba ca), và người xếp lịch nhìn thấy đúng cái bảng họ vẫn dùng hằng tuần.
//
// VÌ SAO DÙNG CHUNG. Trước đây mỗi bảng tự chép lại phần header, và ba bản đã
// lệch nhau: hai bảng vẽ viền tầng màu thương hiệu, bảng thứ ba dùng tên tầng
// viết tắt nên khớp sai. Ba bảng phải "cùng một bảng ở ba chỗ" thì mới có lý do
// bắt người dùng đọc cùng một cách.

import { Fragment, type ReactNode } from "react";
import {
  STATIONS,
  STATION_SEGMENTS,
  FLOOR_BORDER,
  SHIFT_LABEL,
  dayShort,
  fmtDayMonth,
  type CotLich,
  type Station,
} from "../../lib/roster";

// KẺ DỌC Ở ĐÂY LÀ CHỦ Ý, không phải sót lại sau đại tu: bảng này là MA TRẬN
// TOẠ ĐỘ (vị trí × ca) — người đọc dò một hàng vị trí suốt cả tuần, và vách dọc
// là thứ giữ mắt khỏi trượt cột, cùng lý do lưới đặt chỗ rạp phim được giữ
// (DESIGN.md §6). Mực dùng màu trung tính, không dùng mực thương hiệu.
export const O_TREN = "border-b border-r border-hairline";
export const O_DUOI = "border-b border-r border-b-line border-r-hairline";

const TH_BASE =
  "border-b border-r border-hairline px-2 py-2 text-center align-middle font-semibold text-ink";
/** Ba cột đầu dính trái: Tầng · Phòng · Vị trí — đúng ba cột đầu của Excel. */
const DINH = "sticky z-10 bg-surface";
const CO_DINH = [
  { left: "left-0", w: "w-16 min-w-16" },
  { left: "left-16", w: "w-36 min-w-36" },
  { left: "left-52", w: "w-44 min-w-44" },
];

/** Vị trí "Lịch khám" đứng riêng: nó KHÔNG có trong Excel. Xem lib/roster.ts. */
export const VI_TRI_LICH_KHAM = STATIONS.find((s) => s.key === "LICH_KHAM")!;

/** Hai hàng header: ngày (gộp cột theo số ca) rồi tên ca. */
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
            rowSpan={2}
            className={`${DINH} ${CO_DINH[i].left} ${CO_DINH[i].w} z-20 border-b border-r border-hairline bg-surface-muted px-2 py-2 text-left font-semibold text-ink`}
          >
            {t}
          </th>
        ))}
        {cot.map((c) =>
          c.dauNgay ? (
            <th
              key={`${c.date}-ngay`}
              colSpan={c.soCotNgay}
              className={`${TH_BASE} border-l border-l-line`}
              style={{ minWidth: minWidth * c.soCotNgay }}
            >
              <span className="block">{dayShort(c.date)}</span>
              <span className="block text-meta font-normal text-ink-muted">
                {fmtDayMonth(c.date)}
              </span>
            </th>
          ) : null,
        )}
      </tr>
      <tr className="bg-surface-muted">
        {cot.map((c) => (
          <th
            key={`${c.date}-${c.shift}`}
            className={`border-b border-r border-hairline px-2 py-1.5 text-center font-medium text-ink-muted ${
              c.dauNgay ? "border-l border-l-line" : ""
            }`}
            style={{ minWidth }}
          >
            {SHIFT_LABEL[c.shift]}
          </th>
        ))}
      </tr>
    </thead>
  );
}

/** Một hàng cho MỖI vị trí, gộp ô theo Tầng rồi Phòng — đúng hình Excel.
 *
 *  `oCua(vị trí, cột)` trả về đúng một `<td>`. */
export function RosterViTriRows({
  cot,
  oCua,
}: {
  cot: CotLich[];
  oCua: (station: Station, c: CotLich) => ReactNode;
}) {
  return (
    <>
      {STATION_SEGMENTS.map((tang) => {
        let daInTang = false;
        return (
          <Fragment key={tang.floor}>
            {tang.phongs.map((phong) => {
              let daInPhong = false;
              return (
                <Fragment key={`${tang.floor}-${phong.phong}`}>
                  {phong.stations.map((s) => {
                    const inTang = !daInTang;
                    const inPhong = !daInPhong;
                    daInTang = true;
                    daInPhong = true;
                    return (
                      <tr key={s.key} className="align-top">
                        {inTang ? (
                          <td
                            rowSpan={tang.soViTri}
                            className={`${DINH} ${CO_DINH[0].left} ${CO_DINH[0].w} border-b border-r border-hairline border-t-2 px-2 py-2 align-top font-semibold text-ink ${
                              FLOOR_BORDER[tang.floor] ?? "border-t-brand-600"
                            }`}
                          >
                            {tang.floor}
                          </td>
                        ) : null}
                        {inPhong ? (
                          <td
                            rowSpan={phong.stations.length}
                            className={`${DINH} ${CO_DINH[1].left} ${CO_DINH[1].w} border-b border-r border-line px-2 py-2 align-top font-medium text-ink`}
                          >
                            {phong.phong}
                          </td>
                        ) : null}
                        <td
                          className={`${DINH} ${CO_DINH[2].left} ${CO_DINH[2].w} border-b border-r border-hairline px-2 py-2 text-ink-soft`}
                          title={s.label}
                        >
                          {s.short}
                        </td>
                        {cot.map((c) => (
                          <Fragment key={`${s.key}-${c.date}-${c.shift}`}>
                            {oCua(s, c)}
                          </Fragment>
                        ))}
                      </tr>
                    );
                  })}
                </Fragment>
              );
            })}
          </Fragment>
        );
      })}
    </>
  );
}

/** Hàng "Lịch khám" + hàng "Số BS", đứng TRÊN lưới vị trí và tách khỏi nó.
 *
 *  Tách vì chúng trả lời câu khác: lưới dưới nói "chỗ này ai đứng", hai hàng
 *  này nói "hôm nay phòng khám nhận lịch cho những bác sĩ nào". Gộp vào là mời
 *  người ta xếp một bác sĩ vào "Lịch khám" như xếp vào một cái ghế. */
export function RosterLichKhamRows({
  cot,
  oCua,
  demBacSi,
}: {
  cot: CotLich[];
  oCua: (station: Station, c: CotLich) => ReactNode;
  demBacSi: (c: CotLich) => number;
}) {
  return (
    <>
      <tr className="align-top bg-surface-muted/40">
        <td
          colSpan={2}
          className={`${DINH} ${CO_DINH[0].left} border-b border-r border-hairline px-2 py-2 font-semibold text-ink`}
        >
          Lịch khám
        </td>
        <td
          className={`${DINH} ${CO_DINH[2].left} ${CO_DINH[2].w} border-b border-r border-hairline px-2 py-2 text-ink-soft`}
          title={VI_TRI_LICH_KHAM.label}
        >
          Bác sĩ trực
        </td>
        {cot.map((c) => (
          <Fragment key={`lk-${c.date}-${c.shift}`}>
            {oCua(VI_TRI_LICH_KHAM, c)}
          </Fragment>
        ))}
      </tr>
      <tr className="bg-surface-muted/40">
        <td
          colSpan={3}
          className={`${DINH} ${CO_DINH[0].left} border-b border-r border-b-line border-hairline px-2 py-1.5 text-meta text-ink-muted`}
        >
          Số bác sĩ trực
        </td>
        {cot.map((c) => {
          const n = demBacSi(c);
          return (
            <td
              key={`sobs-${c.date}-${c.shift}`}
              className={`${O_DUOI} px-2 py-1.5 text-center font-semibold text-brand-700`}
            >
              {n > 0 ? n : <span className="text-ink-faint">—</span>}
            </td>
          );
        })}
      </tr>
    </>
  );
}
