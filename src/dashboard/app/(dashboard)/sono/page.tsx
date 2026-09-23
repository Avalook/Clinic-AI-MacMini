// ĐÃ GỘP (Tuyền chốt 16/09/2026: không để hai màn cùng làm một việc).
// Điều dưỡng siêu âm (đọc service_log, 0 dòng) → Phòng siêu âm.
// Đường dẫn cũ vẫn mở được — chuyển thẳng sang màn thay thế.

import { redirect } from "next/navigation";

export default function TrangCu() {
  redirect("/phong");
}
