// ĐÃ GỘP 18/09/2026: "Đóng đợt khám" — 0 đợt PENDING_CLOSE trên prod, không code nào còn tạo trạng thái ấy.
// Đường dẫn cũ vẫn mở được — chuyển thẳng sang màn thay thế. Xem docs/SITEMAP.md.

import { redirect } from "next/navigation";

export default function TrangCu() {
  redirect("/customers");
}
