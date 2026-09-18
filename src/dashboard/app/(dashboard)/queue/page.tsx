// ĐÃ GỘP 18/09/2026: "Số thứ tự gọi khám" (ẩn từ 03/07) → Tiếp đón khách.
// Đường dẫn cũ vẫn mở được — chuyển thẳng sang màn thay thế. Xem docs/SITEMAP.md.

import { redirect } from "next/navigation";

export default function TrangCu() {
  redirect("/reception/queue");
}
