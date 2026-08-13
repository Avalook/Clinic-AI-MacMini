// Nhãn "khách mới / khách cũ" cho màn Quản lý khách hàng.
//
// TÁCH KHỎI COMPONENT để chạy được trong `node --test`: bài kiểm không nạp được
// tệp `.tsx` (JSX không phải cú pháp Node hiểu), nên logic thuần nằm trong
// component là logic không ai canh được. Cùng lý do với `lib/luu-nhap.ts`.

/** "Khách mới" hay "Khách cũ · đã khám N lần" — cột riêng cạnh cột trạng thái.
 *
 *  VÌ SAO TÁCH KHỎI CỘT TRẠNG THÁI (Tuyền, 13/08/2026). Hai thứ này trả lời hai
 *  câu hỏi khác nhau và người trực dùng chúng vào hai việc khác nhau:
 *
 *    · Trạng thái = VIỆC PHẢI LÀM bây giờ ("gọi xác nhận lịch", "đã check-in")
 *    · Mới/cũ     = NGƯỜI NÀY LÀ AI — quyết định cách mở lời khi gọi, và bao
 *                   lâu thì xong một ca khám
 *
 *  Nhét chung một ô thì cả hai đều bị đọc lướt: chip trạng thái đã có màu, nhãn
 *  "khám lần 4" nằm cạnh trông như một trạng thái nữa.
 *
 *  ĐẾM LƯỢT ĐÃ KHÁM XONG, không đếm lịch đã đặt. Đặt rồi huỷ thì khách vẫn chưa
 *  từng tới, và gọi họ là "khách cũ đã khám 1 lần" là nói sai với người trực
 *  đang chuẩn bị mở lời.
 *
 *  NHÃN CŨ "khám lần N" / "tái khám" ĐÃ BỎ khỏi màn này cùng lúc: nó nói cùng
 *  một chuyện bằng chữ khác, và để hai chỗ cùng kể một điều là hẹn ngày chúng
 *  lệch nhau. Màn Đặt lịch vẫn có nhãn riêng của nó, đúng chỗ nó cần. */
export function nhanKhachMoiCu(a?: { soLanKham?: number } | null): { dong1: string; dong2: string | null } {
  const soLan = a?.soLanKham ?? 0;
  if (soLan <= 0) return { dong1: "Khách mới", dong2: null };
  return { dong1: "Khách cũ", dong2: `đã khám ${soLan} lần` };
}
