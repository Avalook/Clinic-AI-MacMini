// Lý do xoá tệp kết quả (V9, 30/09/2026) — danh mục gợi ý dùng chung cho MỌI
// nút Xoá tệp (khung tệp phòng dịch vụ, hộp xem, màn Khách hàng, bàn Đối tác).
//
// Máy chủ lưu CHỮ (không lưu mã): lý do bắt buộc và hiện nguyên văn ở lịch sử
// lượt. Danh mục chỉ để bấm cho nhanh; "Khác" thì phải tự viết.

export const LY_DO_XOA_TEP: { ma: string; chu: string }[] = [
  { ma: "NHAM_KHACH", chu: "Tải nhầm khách" },
  { ma: "NHAM_CHI_DINH", chu: "Tải nhầm chỉ định / dịch vụ" },
  { ma: "HONG", chu: "Ảnh mờ, tệp hỏng — sẽ tải lại" },
  { ma: "TRUNG", chu: "Trùng tệp đã tải" },
  { ma: "KHAC", chu: "Lý do khác (tự viết)" },
];

/** Ghép lý do gửi máy chủ: chữ của mục đã chọn + phần ghi thêm. "Khác" thì
 *  chỉ còn phần tự viết. Rỗng = chưa đủ để gửi. */
export function ghepLyDoXoa(ma: string | null, ghi: string): string {
  const them = ghi.trim();
  if (!ma) return "";
  if (ma === "KHAC") return them;
  const chu = LY_DO_XOA_TEP.find((x) => x.ma === ma)?.chu ?? "";
  return them ? `${chu} — ${them}` : chu;
}
