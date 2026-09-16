// ĐÃ GỘP (Tuyền chốt 16/09/2026: không để hai màn cùng làm một việc).
// Bàn khám bác sĩ cũ (thẻ việc + chỉ định trong payload) → Bàn khám theo phòng.
// Đường dẫn cũ vẫn mở được — chuyển thẳng sang màn thay thế.

import { redirect } from "next/navigation";

export default function TrangCu() {
  redirect("/ban-kham");
}
