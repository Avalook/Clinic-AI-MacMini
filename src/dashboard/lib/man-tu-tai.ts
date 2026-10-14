// MÀN TỰ TẢI — những route mà dựng lại trang trên máy chủ (`router.refresh()`) không
// đổi gì trên màn, nên không đáng 800–900ms CPU mỗi lần tin tới.
//
// VÌ SAO (đo prod 14/10/2026). SSR `/phong/{id}` 866ms (tối đa 14,3s), `/ban-kham`
// 880ms (11,3s): nặng nhất hệ thống. Mà phần SERVER của các trang ấy chỉ có kiểm
// quyền vào màn + vài nút theo lego (`requireNavAccess`, `getNutBanKham`,
// `getClinicStaffId`) — không có một dòng dữ liệu sống nào; dữ liệu của màn do
// component client tự tải (`docBang`, `fetch`) và tự nghe tin qua `useNgheBang`.
// Vậy mà `RealtimeRefresher` dựng lại cả trang cho BẤT KỲ bảng nào trong ~47 bảng
// (kể cả `payment`, `staff_task`…), `LiveBoardSync` dựng thêm một lần lúc vào màn,
// và mỗi lần đổi tab lại một lần nữa — trong khi chính các component client đã
// tự hỏi lại đúng thứ chúng vẽ.
//
// MỖI TRANG ĐƯỢC THÊM VÀO ĐÂY PHẢI ĐÚNG LÀ "KHÔNG CÓ DỮ LIỆU SỐNG Ở PHẦN SERVER".
// Trang đọc dữ liệu sống ở server (`/phong` danh sách có số khách, `/reception/queue`,
// `/reception/checkout`, `/truong-ca`) KHÔNG được vào đây — nó chỉ cập nhật nhờ
// `router.refresh()`. Test `tests/tai-lai-dong-loat-boundary.test.mts` canh: trang
// trong danh sách này không được gắn `LiveBoardSync`.
//
// Phần layout dùng chung (thanh bên, chuông cảnh báo lịch bác sĩ từ chối, vị trí
// hôm nay) vẫn có dữ liệu sống nhỏ: `BANG_LAYOUT` giữ cho nó tươi.

const MAN_TU_TAI: readonly RegExp[] = [
  /^\/ban-kham(\/[^/]+)?\/?$/,
  /^\/tu-van\/?$/,
  /^\/phong\/[^/]+\/?$/,
  /^\/hanh-trinh\/?$/,
  /^\/thu-ngan\/(dich-vu|thuoc)(\/lich-su)?\/?$/,
];

/** Bảng mà phần layout (không phải trang) đọc sống: lịch bác sĩ từ chối
 *  (`appointment`) và vị trí/ca trực hôm nay (`work_roster`). */
export const BANG_LAYOUT: readonly string[] = ["appointment", "work_roster"];

/** Route này có tự tải hết dữ liệu sống của nó ở client không. */
export function laManTuTai(pathname: string | null | undefined): boolean {
  if (!pathname) return false;
  return MAN_TU_TAI.some((re) => re.test(pathname));
}

/**
 * Tin bảng `bang` có đáng dựng lại trang ở `pathname` không.
 * `bang === null` = không rõ bảng nào: màn thường thì dựng (an toàn), màn tự tải
 * thì không — nó đã tự hỏi lại qua `useNgheBang`, cũng nhận tin `null` ấy.
 */
export function canDungLaiTrang(
  pathname: string | null | undefined,
  bang: string | null,
  bangCuaMan: ReadonlySet<string>,
): boolean {
  if (!laManTuTai(pathname)) return bang === null || bangCuaMan.has(bang);
  return bang !== null && BANG_LAYOUT.includes(bang) && bangCuaMan.has(bang);
}
