/** Tên phòng để hiện — KHÔNG kèm tầng.
 *
 *  17/09/2026 hàm này in "Tầng 2 · SA1" để Trưởng ca chỉ đường (siêu âm nằm ở
 *  hai tầng). 27/09/2026 (đợt 3) phòng khám yêu cầu ẩn số tầng ở mọi màn: bố
 *  cục phòng đổi liên tục, cột tầng trong cấu hình không theo kịp, và một tầng
 *  sai đọc cho bệnh nhân còn tệ hơn không nói tầng. Tên phòng do quản lý đặt ở
 *  Cấu hình phòng khám — muốn chỉ đường thì đặt tên phòng nói luôn chỗ ấy.
 *  Cột `floor` vẫn giữ trong dữ liệu (màn cấu hình dùng), chỉ không in ra đây.
 */
export function tenPhong(name: string | null | undefined): string {
  return name?.trim() || "—";
}
