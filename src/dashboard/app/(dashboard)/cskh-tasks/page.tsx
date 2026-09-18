// ĐÃ GỘP 18/09/2026: "Nhiệm vụ chăm sóc" đọc cskh_action (0 dòng trên prod) → Quản lý khách hàng.
// Đường dẫn cũ vẫn mở được — chuyển thẳng sang màn thay thế. Xem docs/SITEMAP.md.

import { redirect } from "next/navigation";

export default function TrangCu() {
  redirect("/customers");
}
