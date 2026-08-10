// Hình dạng MỘT DÒNG trong sổ tương tác CSKH — dùng chung giữa màn hình, cột
// trạng thái và truy vấn phía server.
//
// Tách ra một file riêng thay vì để nhờ trong một component. Trước đây kiểu này
// được export từ `GhiTuongTac.tsx`, nên xoá component ấy đi là ba file khác
// gãy theo — một kiểu dữ liệu không nên sống nhờ vòng đời của một khối giao
// diện.

export interface DongLichSu {
  xay_ra_luc: string;
  loai: string;
  kenh: string;
  ket_qua: string | null;
  khach_xac_nhan: boolean | null;
  noi_dung: string | null;
  nhan_vien: string | null;
  nguon: string;
  /** Mã trạng thái mà lần chạm này đóng lại. null = dòng ghi tự do, hoặc dòng
   *  có trước migration 20260810000002. */
  trang_thai_ma?: string | null;
  /** Lượt khám mà lần chạm này thuộc về. null = việc không gắn lịch hẹn nào
   *  (gọi hỏi thăm chung, ghi phản hồi) — những dòng ấy không vào được timeline
   *  của một lượt khám cụ thể, và đó là đúng chứ không phải thiếu. */
  appointment_id?: string | null;
}
