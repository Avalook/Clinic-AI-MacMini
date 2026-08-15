// Khung chung của BA bảng "Lịch làm việc": trang chủ (chỉ đọc), lịch chính thức
// (chỉ đọc), và bảng xếp ca của quản lý.
//
// Form lấy từ file Excel "BẢNG LÀM VIỆC" (sheet LLV):
//   - cột gom theo TẦNG ở hàng header trên,
//   - cột "Số BS" ngay sau Lịch khám,
//   - MỖI NGÀY HAI HÀNG CON, mỗi hàng một người (xem chiaHaiHang trong
//     lib/roster.ts để biết vì sao không phải sáng/chiều).
//
// VÌ SAO DÙNG CHUNG. Trước đây mỗi bảng tự chép lại phần header, và ba bản đã
// lệch nhau: hai bảng vẽ viền tầng màu xanh thương hiệu, bảng thứ ba vẽ theo
// tầng nhưng dùng tên tầng viết tắt nên khớp sai. Ba bảng phải "cùng một bảng ở
// ba chỗ" thì mới có lý do bắt người dùng đọc cùng một cách.

import { Fragment, type ReactNode } from "react";
import { STATIONS, STATION_SEGMENTS, FLOOR_BORDER, type Station } from "../../lib/roster";

// KẺ DỌC Ở ĐÂY LÀ CHỦ Ý, không phải sót lại sau đại tu: bảng này là MA TRẬN
// TOẠ ĐỘ (ngày × trạm) — người đọc dò một cột trạm suốt cả tuần, và vách dọc
// là thứ giữ mắt khỏi trượt cột, cùng lý do lưới đặt chỗ rạp phim được giữ
// (DESIGN.md §6). Cái làm nó "nhìn như Google Sheets" là MỰC MÀU THƯƠNG HIỆU
// kẻ cả hai chiều — nên mực đổi về trung tính, còn hai ĐỘ ĐẬM giữ nguyên vai:
// hairline giữa hai hàng con của một ngày, line đậm hơn đóng một ngày lại.
const TH_BASE =
  "border-b border-r border-hairline px-2 py-2 text-center align-middle font-semibold text-ink";

/** Viền dưới của hàng con TRÊN — nhạt, để hai hàng của một ngày đọc như một khối. */
export const O_TREN = "border-b border-r border-hairline";
/** Viền dưới của hàng con DƯỚI — đậm, đóng lại một ngày. */
export const O_DUOI = "border-b border-r border-b-line border-r-hairline";

/** Hai hàng header: tầng (gộp cột) rồi tên trạm. Cột "Ngày" và "Số BS" gộp dọc. */
export function RosterGridHead({ minWidth = 92 }: { minWidth?: number }) {
  return (
    <thead>
      <tr className="bg-surface-muted">
        <th
          rowSpan={2}
          className="sticky left-0 z-20 border-b border-r border-hairline bg-surface-muted px-2 py-2 text-left font-semibold text-ink"
        >
          Ngày
        </th>
        {STATION_SEGMENTS.map((seg) =>
          seg.floor === "" ? (
            <Fragment key="khong-tang">
              {seg.stations.map((s) => (
                <th
                  key={s.key}
                  rowSpan={2}
                  className={TH_BASE}
                  style={{ minWidth: minWidth + 18 }}
                >
                  {s.short}
                </th>
              ))}
              <th
                rowSpan={2}
                className={`min-w-13 ${TH_BASE}`}
                title="Số bác sĩ trực trong ngày — tính từ cột Lịch khám"
              >
                Số BS
              </th>
            </Fragment>
          ) : (
            <th
              key={seg.floor}
              colSpan={seg.stations.length}
              className={`${TH_BASE} border-t-2 ${FLOOR_BORDER[seg.floor] ?? "border-t-brand-600"}`}
            >
              {seg.floor}
            </th>
          ),
        )}
      </tr>
      <tr className="bg-surface-muted">
        {STATIONS.filter((s) => s.floor !== "").map((s) => (
          <th
            key={s.key}
            className="border-b border-r border-hairline px-2 py-1.5 text-center font-medium text-ink-muted"
            style={{ minWidth }}
          >
            {s.short}
          </th>
        ))}
      </tr>
    </thead>
  );
}

/** Hai hàng <tr> của MỘT ngày. `oCua(trạm, hàng)` trả về đúng một <td>. */
export function RosterDayRows({
  nhan,
  soBacSi,
  vach,
  oCua,
}: {
  /** Nhãn cột đầu, vd "T2 · 03/08". */
  nhan: string;
  soBacSi: number;
  /** Class nền so le của ngày này. */
  vach: string;
  oCua: (station: Station, hang: 0 | 1) => ReactNode;
}) {
  return (
    <>
      <tr className={"align-top " + vach}>
        <td
          rowSpan={2}
          className="sticky left-0 z-10 whitespace-nowrap border-b border-r border-hairline bg-inherit px-2 py-2 font-medium text-ink"
        >
          {nhan}
        </td>
        {STATIONS.map((s) => (
          <Fragment key={s.key}>
            {oCua(s, 0)}
            {s.key === "LICH_KHAM" && (
              <td
                rowSpan={2}
                className={`${O_DUOI} px-2 py-2 text-center font-semibold text-brand-700`}
              >
                {soBacSi > 0 ? soBacSi : <span className="text-ink-faint">—</span>}
              </td>
            )}
          </Fragment>
        ))}
      </tr>
      <tr className={"align-top " + vach}>
        {STATIONS.map((s) => (
          <Fragment key={s.key}>{oCua(s, 1)}</Fragment>
        ))}
      </tr>
    </>
  );
}
