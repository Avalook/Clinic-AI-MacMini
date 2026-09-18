// ĐÃ GỘP 18/09/2026: "Sức khoẻ API" thành một tab của Vận hành hệ thống.
// Đường dẫn cũ vẫn mở được — chuyển thẳng sang màn thay thế. Xem docs/SITEMAP.md.

import { redirect } from "next/navigation";

export default function TrangCu() {
  redirect("/ops?tab=api");
}
