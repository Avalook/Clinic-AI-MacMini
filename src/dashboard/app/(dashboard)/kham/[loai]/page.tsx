// ĐÃ GỘP (Tuyền chốt 16/09/2026: không để hai màn cùng làm một việc).
// Năm màn Khám nội tiết/phụ khoa/sản/hiếm muộn/nam khoa → Bàn khám (phiếu mở theo dịch vụ khách đặt).
// Đường dẫn cũ vẫn mở được — chuyển thẳng sang màn thay thế.

import { redirect } from "next/navigation";

export default function TrangCu() {
  redirect("/ban-kham");
}
