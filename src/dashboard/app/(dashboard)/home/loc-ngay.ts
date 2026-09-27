// CHỌN MỘT NGÀY TRONG BẢNG LỊCH HẸN TUẦN — hàm thuần (27/09/2026, đợt 3).
//
// Góp ý phòng khám: "Trang chủ: check đặt lịch cần hiển thị theo ngày". Bảng
// "Lịch hẹn khám" vẽ bảy ngày chồng dọc; người ở quầy chỉ cần MỘT ngày. Hàng
// chip T2…CN + "Cả tuần" lọc ngày ngay ở trình duyệt (dữ liệu cả tuần đã về
// trong một gói), lựa chọn giữ trên thanh địa chỉ `?ngay=YYYY-MM-DD` để tải
// lại / gửi link vẫn đúng ngày.
//
// Tham số lấy thẳng từ thanh địa chỉ nên RÁC PHẢI BỊ BỎ QUA, KHÔNG ĐƯỢC NÉM
// (CLAUDE.md: ba lần 500 vì luật này) — rác thì rơi về mặc định.

import { dayShort, fmtDayMonth } from "../../../lib/roster.ts";

/** Giá trị `?ngay=` cho "Cả tuần" — cần viết ra được vì mặc định của tuần
 *  này là HÔM NAY, không phải cả tuần. */
export const CA_TUAN = "ca-tuan";

/** Đúng một ngày lịch có thật dạng YYYY-MM-DD (không nhận 2026-02-30). */
function laNgayThat(s: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(`${s}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}

/** Ngày đang chọn của bảng — `null` nghĩa là CẢ TUẦN.
 *
 *  - `?ngay=ca-tuan` → cả tuần;
 *  - `?ngay=` là một ngày NẰM TRONG tuần đang xem → ngày ấy;
 *  - không có, rác, hoặc ngày của TUẦN KHÁC → mặc định: hôm nay nếu tuần đang
 *    xem là tuần này (giờ VN — `homNay` do người gọi đưa, `todayVn()`), còn
 *    tuần khác thì cả tuần. */
export function ngayDangChon(
  thamSo: string | null | undefined,
  ngayTrongTuan: readonly string[],
  homNay: string,
): string | null {
  const macDinh = ngayTrongTuan.includes(homNay) ? homNay : null;
  if (typeof thamSo !== "string") return macDinh;
  const s = thamSo.trim();
  if (s === CA_TUAN) return null;
  if (!laNgayThat(s)) return macDinh;
  return ngayTrongTuan.includes(s) ? s : macDinh;
}

/** Lọc danh sách ngày theo lựa chọn. `null` = giữ cả tuần. */
export function locTheoNgay<T extends { date: string }>(
  days: readonly T[],
  ngay: string | null,
): T[] {
  return ngay === null ? [...days] : days.filter((d) => d.date === ngay);
}

/** Các tab của dải chọn ngày: "Cả tuần" rồi T2…CN kèm NGÀY TRONG THÁNG; số
 *  lịch để riêng (`so`) — dải vẽ nó thành huy hiệu nhạt, không dính vào chữ
 *  (27/09/2026: "T5 01 3" đọc thành một con số). */
export function tabNgay(
  days: readonly { date: string; items: readonly unknown[] }[],
): { ma: string; nhan: string; so: number; title?: string }[] {
  return [
    { ma: CA_TUAN, nhan: "Cả tuần", so: 0 },
    ...days.map((d) => ({
      ma: d.date,
      nhan: `${dayShort(d.date)} ${d.date.slice(8)}`,
      so: d.items.length,
      title: `${fmtDayMonth(d.date)} · ${d.items.length} lịch hẹn`,
    })),
  ];
}
