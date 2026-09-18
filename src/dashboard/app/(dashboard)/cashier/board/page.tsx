// ĐÃ GỘP 18/09/2026: bản thứ ba của cùng quầy thu (QuayThuNgan) → Thu tiền dịch vụ.
// Đường dẫn cũ vẫn mở được — chuyển thẳng sang màn thay thế. Xem docs/SITEMAP.md.

import { redirect } from "next/navigation";

export default function TrangCu() {
  redirect("/thu-ngan/dich-vu");
}
