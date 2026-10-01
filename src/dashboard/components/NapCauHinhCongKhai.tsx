"use client";

// Đặt cấu hình công khai (URL Supabase, khoá anon, môi trường…) cho mã TRÌNH
// DUYỆT — ngay trong lượt render đầu, trước mọi component con. Đặt trong lúc
// render (không trong useEffect) có chủ ý: con của nó render NGAY SAU và có thể
// gọi `cauHinhCongKhai()` đồng bộ; effect thì chạy quá muộn. Hàm đặt là luỹ
// đẳng và không làm gì ở máy chủ. Xem lib/cau-hinh-cong-khai.ts.

import {
  datCauHinhCongKhai,
  type CauHinhCongKhai,
} from "@/lib/cau-hinh-cong-khai";

export function NapCauHinhCongKhai({ cauHinh }: { cauHinh: CauHinhCongKhai }) {
  datCauHinhCongKhai(cauHinh);
  return null;
}
