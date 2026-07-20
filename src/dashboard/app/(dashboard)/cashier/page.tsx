// Trang gộp Thu ngân CŨ đã tách thành Bảng giá thuốc (/cashier/thuoc) +
// Bảng giá dịch vụ (/cashier/dich-vu) (T-DASH-CASHIER-IA-02). Giữ /cashier như
// lối vào cũ → chuyển hướng sang Bảng giá thuốc để link cũ không gãy.

import { redirect } from "next/navigation";

export default function CashierIndexPage() {
  redirect("/cashier/thuoc");
}
