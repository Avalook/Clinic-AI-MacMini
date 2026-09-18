// ĐÃ GỘP 18/09/2026: "Command Center" thành tab Toàn cảnh của Vận hành hệ thống.
// Đường dẫn cũ vẫn mở được — chuyển thẳng sang màn thay thế. Xem docs/SITEMAP.md.

import { redirect } from "next/navigation";

export default function TrangCu() {
  redirect("/ops?tab=toan-canh");
}
