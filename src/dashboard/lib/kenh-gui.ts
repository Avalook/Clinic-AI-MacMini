// Chữ hiển thị của kênh đã gửi tệp kết quả (`tep_ket_qua.gui_kenh`) — MỘT bảng cho mọi
// màn (ô chọn kênh khi gửi + chữ "đã gửi qua …"), để màn không in mã thô ("ZALO").
// NGOAI_HE_THONG = lệnh bù 12/11/2026: kết quả email cũ nhân viên đã trả trước khi có
// hệ thống — KHÔNG phải kênh để chọn khi gửi (KENH_GUI không có nó).
export const KENH_GUI: [string, string][] = [
  ["ZALO", "Zalo"],
  ["SMS", "SMS"],
  ["TRUC_TIEP", "Đưa trực tiếp"],
  ["EMAIL", "Email"],
];

/** Kênh chọn được ở nút "Đã gửi kết quả cho bệnh nhân" của màn Quản lý khách hàng: nút
 *  ghi vào SỔ CSKH (`tuong_tac_cskh.kenh`, CHECK chưa có EMAIL) rồi máy chủ ghi đã gửi
 *  tờ với đúng kênh đó. Email chỉ chọn được ở thẻ việc / từng tệp. */
export const KENH_GUI_SO_CSKH = KENH_GUI.filter(([ma]) => ma !== "EMAIL");

export const KENH_NGOAI_HE_THONG = "NGOAI_HE_THONG";

const TEN: Record<string, string> = {
  ...Object.fromEntries(KENH_GUI),
  [KENH_NGOAI_HE_THONG]: "ngoài hệ thống",
};

export function tenKenhGui(kenh: string): string {
  return TEN[kenh] ?? kenh;
}
