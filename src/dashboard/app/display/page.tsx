// Màn hình TV phòng chờ — bảng gọi số theo khu.
//
// ĐỌC QUA BACKEND, không đọc thẳng Supabase nữa. Ba lý do, theo thứ tự quan
// trọng:
//
// ① THỨ TỰ. Trang này từng xếp bằng `slot_start` thuần, trong khi bảng của Lễ
//    tân và của bác sĩ xếp theo LUẬT GỌI. Hai bảng nói hai thứ tự khác nhau, và
//    người ngồi chờ đọc bảng nào cũng thấy có lý — cho tới lúc bị gọi sai lượt.
//
// ② KHÔNG DANH TÍNH. Nguyên tắc cũ đúng và được giữ nguyên: thứ gì trang này
//    TẢI VỀ là thứ công khai, nên "không render" chưa đủ. Nay việc lọc nằm ở
//    backend (display_board_service) chứ không ở câu `.select()` — một chỗ có
//    bài kiểm canh, thay vì một danh sách cột dễ ai đó thêm vào cho tiện.
//
// ③ KHU VỰC. Việc xếp dịch vụ vào khu từng là một phép dò từ khoá viết cứng
//    trong TSX, và nó SAI với khu siêu âm suốt (xem ghi chú ở
//    display_board_service._khop_vao_khu_that).
//
// Trang vẫn CẦN ĐĂNG NHẬP, y như thực tế hôm nay: chú thích cũ ghi "public,
// không cần đăng nhập" nhưng RLS trên `appointment` khiến trình duyệt chưa đăng
// nhập đọc ra 0 dòng — nghĩa là máy tivi vốn đã phải đăng nhập bằng một tài
// khoản nhân viên. Mở thật ra công cộng là một quyết định về bảo mật riêng, cần
// chủ phòng khám gật đầu, không phải hệ quả phụ của việc sửa thứ tự sắp xếp.

import { fetchFromBackend } from "../../lib/backend-proxy";
import DisplayBoard, { type DisplayZone, type DisplayItem } from "./DisplayBoard";

export const dynamic = "force-dynamic";

export default async function DisplayPage() {
  const data = await fetchFromBackend<{
    zones: DisplayZone[];
    items: DisplayItem[];
    clinic_name?: string;
    footer_text?: string;
    footer_info?: string;
  }>("/api/v1/display/queue");

  // `null` = KHÔNG HỎI ĐƯỢC backend, khác hẳn `items: []` = hôm nay chưa ai đến.
  // Trên một màn hình treo giữa phòng chờ, hai thứ đó mà hiện giống nhau thì
  // hỏng có thể kéo dài cả ngày mà không ai biết.
  if (!data) {
    return (
      <div className="flex h-screen items-center justify-center bg-ink text-white">
        <p className="text-lg">Chưa kết nối được máy chủ — bảng số tạm dừng.</p>
      </div>
    );
  }

  return (
    <DisplayBoard
      zones={data.zones}
      items={data.items}
      clinicName={data.clinic_name}
      footerText={data.footer_text}
      footerInfo={data.footer_info}
    />
  );
}
