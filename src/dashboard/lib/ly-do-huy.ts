// Lý do huỷ lịch — danh mục dùng chung cho MỌI màn có nút huỷ.
//
// Ba mã đầu là BA THỜI ĐIỂM trong vòng đời lịch hẹn, không phải ba cách nói của
// "khách bận" — và mỗi thời điểm tốn của phòng khám một khoản khác nhau: báo
// lúc gọi xác nhận thì chỗ đó còn bán lại được, báo vào đúng giờ khám thì bác
// sĩ ngồi không và chỗ mất trắng. Đếm được ba con số ấy mới biết nên siết khâu
// nào; gộp vào một ô chữ tự do thì không.
//
// CHỮ Ở ĐÂY PHẢI KHỚP `LY_DO_HUY` trong `clinicai/services/booking_service.py`.
// Ba màn cùng vẽ danh sách này (Quản lý khách hàng, Công việc của tôi, và màn
// hiển thị lịch đã huỷ), nên chép tay là sớm muộn mỗi màn nói một kiểu về cùng
// một lần huỷ. Bài kiểm chống lệch: src/tests/unit/test_ly_do_huy_drift.py

export const LY_DO_HUY: Record<string, string> = {
  BAO_KHI_XAC_NHAN: "Gọi xác nhận trước 7 ngày — khách báo không đến được",
  BAO_KHI_NHAC_HEN: "Đã xác nhận sẽ đến, tới lúc nhắc hẹn thì báo không đến",
  BAO_VAO_GIO_KHAM: "Đúng giờ khám, lễ tân gọi khách mới báo không đến",
  KHAC: "Lý do khác (tự viết)",
};

/** Thứ tự vẽ trên ô chọn — theo thời điểm xảy ra, sớm trước. */
export const LY_DO_HUY_THU_TU: string[] = [
  "BAO_KHI_XAC_NHAN",
  "BAO_KHI_NHAC_HEN",
  "BAO_VAO_GIO_KHAM",
  "KHAC",
];

/** Nhãn để hiển thị một lần huỷ đã ghi. Mã lạ thì in nguyên mã còn hơn in "—". */
export function nhanLyDoHuy(ma: string | null | undefined): string | null {
  if (!ma) return null;
  return LY_DO_HUY[ma] ?? ma;
}
