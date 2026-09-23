// ĐÃ GỘP (Tuyền chốt 16/09/2026: không để hai màn cùng làm một việc).
// Làm thủ thuật & dịch vụ (service_log) → Phòng thủ thuật; thủ thuật do bác sĩ làm.
// Đường dẫn cũ vẫn mở được — chuyển thẳng sang màn thay thế.

import { redirect } from "next/navigation";

export default function TrangCu() {
  redirect("/phong");
}
