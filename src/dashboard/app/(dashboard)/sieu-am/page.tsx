// ĐÃ GỘP (Tuyền chốt 16/09/2026: không để hai màn cùng làm một việc).
// Khám siêu âm (ultrasound_record) → Phòng siêu âm: hàng chờ theo chỉ định.
// Đường dẫn cũ vẫn mở được — chuyển thẳng sang màn thay thế.

import { redirect } from "next/navigation";

export default function TrangCu() {
  redirect("/phong");
}
