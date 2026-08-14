// Cách gọi tên "lịch này là khám mới hay khám cũ" — MỘT chỗ duy nhất.
//
// Backend trả nguyên văn "Khám lần đầu" / "Tái khám" (week_appointments_service
// tính từ lịch hẹn sớm nhất của khách). Tuyền đổi cách gọi ngày 14/08/2026 sang
// "Khám mới" / "Khám cũ" cho khớp với cột Khách mới/Khách cũ ở màn Khách hàng —
// người trực đọc hai màn trong cùng một ca, hai bộ từ vựng cho cùng một khái
// niệm là bắt họ dịch trong đầu.
//
// ĐỔI Ở ĐÂY, KHÔNG ĐỔI Ở BACKEND. Giá trị backend trả là DỮ LIỆU, đi vào so
// sánh và vào các màn khác; chữ hiển thị là CHUYỆN CỦA GIAO DIỆN. Đổi ở backend
// thì mọi phép so `=== "Khám lần đầu"` rải rác trong ba màn lặng lẽ sai — không
// màn nào báo lỗi, chỉ là mọi lịch đều tô một màu.
//
// Cũng vì thế hàm này nhận CẢ HAI cách gọi: dữ liệu cũ còn nằm trong bộ nhớ
// trình duyệt hay trong một phản hồi đang bay vẫn hiện đúng.

/** Nhãn hiển thị cho một giá trị `phan_loai` của backend. */
export function nhanPhanLoaiKham(value: string | null | undefined): string {
  switch ((value ?? "").trim()) {
    case "Khám lần đầu":
    case "Khám mới":
      return "Khám mới";
    case "Tái khám":
    case "Khám cũ":
      return "Khám cũ";
    default:
      // "Chưa khám" (màn Danh sách bệnh nhân) và chuỗi rỗng đi thẳng qua: chuỗi
      // rỗng nghĩa là chưa suy ra được, và màn hình vẽ dấu "—" cho nó.
      return (value ?? "").trim();
  }
}

/** Lịch này có phải LẦN ĐẦU của khách không — dùng để tô màu và để đếm.
 *
 *  Tách khỏi nhãn hiển thị: đổi chữ trên màn hình không được làm phép đếm sai.
 */
export function laKhamMoi(value: string | null | undefined): boolean {
  return nhanPhanLoaiKham(value) === "Khám mới";
}

/** Lịch của khách đã từng tới. Không phải "không phải khám mới": chuỗi rỗng và
 *  "Chưa khám" không thuộc về bên nào, và gộp chúng vào đây làm phồng số khám
 *  cũ trong bảng thống kê. */
export function laKhamCu(value: string | null | undefined): boolean {
  return nhanPhanLoaiKham(value) === "Khám cũ";
}
