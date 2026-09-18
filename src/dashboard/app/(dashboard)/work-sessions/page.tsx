// ĐÃ GỘP 18/09/2026: "Buổi làm việc" — bảng work_session 0 dòng trên prod; ca làm việc ở Lịch làm việc.
// Đường dẫn cũ vẫn mở được — chuyển thẳng sang màn thay thế. Xem docs/SITEMAP.md.

import { redirect } from "next/navigation";

export default function TrangCu() {
  redirect("/schedule");
}
