// Khung chung của BA bảng "Lịch làm việc": trang chủ (chỉ đọc), lịch chính thức
// (chỉ đọc), và bảng xếp ca của quản lý.
//
// Y HỆT FILE EXCEL xếp lịch của PK Kim Ngưu (Tuyền 16/09/2026: "bảng nó phải
// dạng y hệt như này"):
//
//   • ba cột trái  Tầng · Phòng · Vị trí nhân sự
//   • ba hàng đầu  Thứ · ngày · ca     (T2→T6 một ca Tối; T7, CN ba ca)
//   • nền theo PHÒNG, đúng mã màu Excel
//   • vạch xanh đậm ngăn giữa các tầng
//   • ô ĐEN      = vị trí không làm ca ấy   (khác ô trống = cần người, chưa xếp)
//   • khối NGHỈ  = cả ca phòng khám nghỉ
//   • ô GỘP DỌC  = một người đứng hai vị trí liền nhau (Lễ tân + Thu ngân…)
//
// GỘP DỌC SUY RA TỪ DỮ LIỆU, không khai tay. Đọc file Excel thì ô gộp dọc chỉ
// xảy ra ở bốn cặp — Lễ tân+Thu ngân, Xếp thuốc+Tạo đơn, Đo chỉ số+Lấy mẫu, Hỏi
// bệnh+Thư ký — và nghĩa của nó luôn là "cùng một người đứng cả hai". Nên luật
// là: hai vị trí LIỀN NHAU trong CÙNG tầng có CÙNG người → một ô. Không cần danh
// sách cặp; ngày phòng khám gộp một cặp mới, bảng tự gộp theo.

import { Fragment, type ReactNode } from "react";
import {
  MAU_PHONG,
  SHIFT_LABEL,
  dayShort,
  phanTang,
  fmtDayMonth,
  type CotLich,
  type Station,
} from "../../lib/roster";

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

/** Ba cột trái dính khi cuộn ngang. */
const COT_TRAI = [
  "sticky left-0 z-10 w-16 min-w-16",
  "sticky left-16 z-10 w-40 min-w-40",
  "sticky left-56 z-10 w-56 min-w-56",
];
const KE = "border border-line-strong";

export type TrangThaiO = "DONG" | "NGHI" | null;

export interface ThongTinO {
  /** Ô đen / khối nghỉ / bình thường. */
  dong: TrangThaiO;
  /** Khoá so sánh để gộp dọc: cùng khoá (khác rỗng) = cùng người. */
  khoa: string;
}

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
            className={`${COT_TRAI[i]} z-20 ${KE} bg-surface-muted px-2 py-2 text-center align-middle font-semibold text-ink`}
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

/** Thân bảng: mỗi vị trí một hàng, gộp Tầng/Phòng, vạch tầng, ô đen, NGHỈ, gộp dọc.
 *
 *  `thongTin(vị trí, cột)` nói ô ấy đóng hay mở và ai đứng (khoá để gộp).
 *  `veO(vị trí, cột, rowSpan)` vẽ nội dung một ô MỞ — trả về đúng một `<td>`. */
export function RosterViTriRows({
  stations,
  cot,
  thongTin,
  veO,
}: {
  /** Danh mục vị trí từ database (`viTriTuDb`), theo thứ tự dòng Excel. */
  stations: readonly Station[];
  cot: CotLich[];
  thongTin: (station: Station, c: CotLich) => ThongTinO;
  veO: (station: Station, c: CotLich, rowSpan: number) => ReactNode;
}) {
  const tongCot = 3 + cot.length;
  const cacTang = phanTang(stations);
  return (
    <>
      {cacTang.map((tang, ti) => {
        const viTri = tang.phongs.flatMap((p) => p.stations);

        // ── Tính trước, theo từng cột: ô nào bị gộp vào ô trên, ô nào dài bao nhiêu.
        // `span[i][ci]` = rowSpan của ô ở hàng i (0 = ô này đã bị gộp, không vẽ).
        const span: number[][] = viTri.map(() => cot.map(() => 1));
        const nghiCaTang: boolean[] = cot.map(
          (c) => viTri.length > 0 && viTri.every((s) => thongTin(s, c).dong === "NGHI"),
        );
        cot.forEach((c, ci) => {
          if (nghiCaTang[ci]) {
            span[0][ci] = viTri.length;
            for (let i = 1; i < viTri.length; i++) span[i][ci] = 0;
            return;
          }
          let dau = 0;
          for (let i = 1; i < viTri.length; i++) {
            const tren = thongTin(viTri[dau], c);
            const duoi = thongTin(viTri[i], c);
            const gop =
              tren.dong === null &&
              duoi.dong === null &&
              tren.khoa !== "" &&
              tren.khoa === duoi.khoa;
            if (gop) {
              span[dau][ci] += 1;
              span[i][ci] = 0;
            } else {
              dau = i;
            }
          }
        });

        let daInTang = false;
        let chiSo = -1;
        return (
          <Fragment key={tang.floor}>
            {tang.phongs.map((phong) => {
              let daInPhong = false;
              const mau = MAU_PHONG[phong.phong] ?? "bg-surface";
              return (
                <Fragment key={`${tang.floor}-${phong.phong}-${phong.stations[0].key}`}>
                  {phong.stations.map((s) => {
                    chiSo += 1;
                    const i = chiSo;
                    const inTang = !daInTang;
                    const inPhong = !daInPhong;
                    daInTang = true;
                    daInPhong = true;
                    return (
                      <tr key={s.key} className="align-middle">
                        {inTang ? (
                          <td
                            rowSpan={tang.soViTri}
                            className={`${COT_TRAI[0]} ${KE} bg-surface px-2 py-2 align-top font-semibold text-ink`}
                          >
                            {tang.floor}
                          </td>
                        ) : null}
                        {inPhong ? (
                          <td
                            rowSpan={phong.stations.length}
                            className={`${COT_TRAI[1]} ${KE} ${mau} px-2 py-2 font-semibold text-ink`}
                          >
                            {phong.phong}
                          </td>
                        ) : null}
                        <td
                          className={`${COT_TRAI[2]} ${KE} ${mau} px-2 py-1 text-ink`}
                          title={s.label}
                        >
                          {s.short}
                        </td>
                        {cot.map((c, ci) => {
                          const rs = span[i][ci];
                          if (rs === 0) return null;
                          const k = `${s.key}-${c.date}-${c.shift}`;
                          if (nghiCaTang[ci]) {
                            return (
                              <td
                                key={k}
                                rowSpan={rs}
                                className={`${KE} bg-lich-nghi text-center align-middle text-2xl font-bold text-warning-bg`}
                              >
                                NGHỈ
                              </td>
                            );
                          }
                          const tt = thongTin(s, c);
                          if (tt.dong) {
                            return (
                              <td
                                key={k}
                                rowSpan={rs}
                                className={`${KE} ${tt.dong === "NGHI" ? "bg-lich-nghi" : "bg-lich-dong"}`}
                                aria-label="Không làm ca này"
                              />
                            );
                          }
                          return <Fragment key={k}>{veO(s, c, rs)}</Fragment>;
                        })}
                      </tr>
                    );
                  })}
                </Fragment>
              );
            })}
            {/* Vạch xanh đậm ngăn tầng — đúng hàng kẻ màu `073763` trong Excel. */}
            {ti < cacTang.length - 1 ? (
              <tr aria-hidden="true">
                <td colSpan={tongCot} className="h-3 bg-lich-vach-tang p-0" />
              </tr>
            ) : null}
          </Fragment>
        );
      })}
    </>
  );
}

/** Nền của một ô MỞ: màu phòng của vị trí ấy, như Excel. */
export function nenO(station: Station): string {
  return MAU_PHONG[station.phong] ?? "bg-surface";
}
