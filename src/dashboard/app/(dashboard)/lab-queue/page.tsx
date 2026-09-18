// ĐÃ GỘP (Tuyền chốt 16/09/2026: không để hai màn cùng làm một việc).
// Lấy mẫu xét nghiệm (lab_result) → phòng Lấy mẫu theo chỉ định.
// Đường dẫn cũ vẫn mở được — chuyển thẳng sang màn thay thế.

import { redirect } from "next/navigation";

export default function TrangCu() {
  redirect("/phong/KN-LAYMAU");
}
