// QUYỀN Ở PHÍA TRÌNH DUYỆT — hàm thuần, không gọi mạng (27/09/2026, đợt 3).
//
// Danh sách capability đã có sẵn: layout đọc `GET /phan-quyen/toi` một lần mỗi
// lượt dựng trang và đưa xuống `Shell` (prop `quyen`), `Shell` phát lại qua
// `QuyenContext`. File này chỉ HỎI danh sách ấy — nên component client nào
// cũng biết "tài khoản này có lego X không" mà không `if` theo vai.
//
// Ẩn/hiện KHÔNG phải bảo mật: máy chủ vẫn tự kiểm quyền ở mọi lệnh. File này
// không được import thứ gì của máy chủ (`backend-proxy`, `next/headers`…) vì
// nó chạy trong trình duyệt.

/** Quyền đóng lượt (check-out). Khớp `_RECEPTION_GUARD` ở
 *  `src/clinicai/api/v1/routers/dispatch.py` — cùng lego 1 "Tiếp đón khách". */
export const QUYEN_CHECK_OUT = "reception.checkin.perform";

/** Có quyền `ma` không. `null` (máy chủ chưa trả lời quyền) → KHÔNG: nút hành
 *  động ẩn đi thay vì hiện ra rồi bị từ chối. */
export function coQuyen(
  quyen: readonly string[] | null | undefined,
  ma: string,
): boolean {
  return Array.isArray(quyen) && quyen.includes(ma);
}

/** Được bấm Check-out (đóng lượt) không. */
export function checkOutDuoc(quyen: readonly string[] | null | undefined): boolean {
  return coQuyen(quyen, QUYEN_CHECK_OUT);
}
