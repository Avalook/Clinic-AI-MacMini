// Chữ hiển thị của kênh đã gửi tệp kết quả (`tep_ket_qua.gui_kenh`). Chỉ là nhãn để màn
// không in mã thô ("ZALO", "NGOAI_HE_THONG"). NGOAI_HE_THONG = lệnh bù 12/11/2026: kết
// quả email cũ nhân viên đã trả trước khi có hệ thống (không phải kênh để chọn khi gửi).
const TEN: Record<string, string> = {
  ZALO: "Zalo",
  SMS: "SMS",
  TRUC_TIEP: "đưa trực tiếp",
  EMAIL: "Email",
  NGOAI_HE_THONG: "đã trả ngoài hệ thống",
};

export function tenKenhGui(kenh: string): string {
  return TEN[kenh] ?? kenh;
}
