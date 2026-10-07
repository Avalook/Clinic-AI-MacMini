// Ô tìm khách ở màn phòng dịch vụ (Tuyền 07/10/2026: "chưa có thanh tìm kiếm ở
// các phòng dịch vụ — bất tiện lắm"). Lọc TẠI CHỖ trên danh sách máy chủ đã
// trả (khách hôm nay của phòng) — không gọi thêm API, không quyết gì nghiệp vụ.

import { chuanHoa } from "./tiep-don.ts";

export interface KhachTim {
  ten: string | null | undefined;
  ma: string | null | undefined;
  /** Số tiếp đón, số booking, số thứ tự — gõ "10" hay "#10" là ra khách số 10. */
  so: ReadonlyArray<number | null | undefined>;
}

/** Khách có khớp ô tìm không. Rỗng = khớp hết.
 *
 * - Gõ chữ (bỏ dấu, không phân biệt hoa thường): khớp tên hoặc mã khách, mọi
 *   từ gõ vào phải có mặt ("ngoc mai" khớp "Bùi Thị Ngọc Mai").
 * - Gõ số ngắn (≤ 3 chữ số, có hay không "#"): khớp ĐÚNG số tiếp đón / booking /
 *   thứ tự — "1" không được kéo theo khách số 10, 11, 12…; vẫn khớp nếu tên/mã
 *   chứa nguyên cụm đó ("Khách 0141" gõ "141" ra ngay).
 */
export function khopTimKhach(kim: string, k: KhachTim): boolean {
  const tim = chuanHoa(kim).replace(/^#/, "");
  if (!tim) return true;
  const chu = chuanHoa([k.ten, k.ma].filter(Boolean).join(" "));
  if (/^\d{1,3}$/.test(tim)) {
    const n = Number(tim);
    if (k.so.some((s) => s === n)) return true;
    // Từ trong tên/mã bằng đúng số gõ (bỏ số 0 đầu): "0141" khớp "141".
    return chu.split(/[\s\-_.]+/).some((tu) => /^\d+$/.test(tu) && Number(tu) === n);
  }
  return tim.split(" ").every((tu) => chu.includes(tu));
}
