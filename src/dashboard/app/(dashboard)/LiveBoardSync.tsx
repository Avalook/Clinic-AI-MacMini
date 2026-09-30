"use client";

// GẮN VÀO MÀN CẦN LUÔN ĐÚNG THỜI ĐIỂM — hàng đợi, check-out, điều phối.
//
// HAI LỖ MÀ REALTIME KHÔNG BỊT ĐƯỢC.
//
// 1. RealtimeRefresher gọi `router.refresh()`, và refresh chỉ làm mới TRANG
//    ĐANG MỞ. Bộ nhớ đệm điều hướng của Next giữ trang khác trong 10 giây
//    (`staleTimes.dynamic`, đặt ở next.config.ts để chuyển trang bớt giật).
//
//    Nên: lễ tân đang ở hàng đợi → nhảy sang màn khác → bác sĩ khám xong một
//    người → quay lại hàng đợi trong vòng 10 giây → THẤY BẢN CŨ. Bệnh nhân đã
//    xong vẫn nằm trong danh sách chờ, và người đứng ở quầy là người phát hiện
//    ra trước.
//
// 2. Đổi sang tab khác hoặc khoá màn hình thì trình duyệt bóp websocket. Quay
//    lại, kênh có thể đã rớt và phải chờ tới nhịp lưới an toàn (60 giây) mới
//    biết mình đang nhìn dữ liệu cũ.
//
// Cách bịt: làm mới khi VÀO màn, và làm mới khi màn được nhìn lại. Cả hai đều
// là lúc con người đang thật sự đọc — đúng thời điểm dữ liệu cần đúng, và
// không phải một vòng đếm giây chạy suốt ngày.
//
// LỖ 2 NAY DO `RealtimeRefresher` BỊT (30/09/2026). Bản trước file này tự nghe
// `visibilitychange` LẪN `focus` và gọi `router.refresh()` cho mỗi cái — cộng
// với lần bắt kịp của `RealtimeRefresher` là BA lần dựng lại cả trang cho một
// lần đổi tab (đo prod 30/09: nhân viên đổi tab liên tục, dòng SSE sống trung
// vị 9 giây). `RealtimeRefresher` gắn ở layout nên có mặt trên mọi màn dán file
// này, và nó đã làm mới đúng một lượt mỗi khi tab hiện lại (gộp tối đa một lần
// mỗi 2 giây — `lib/nhip-khi-hien`). `focus` mà không kèm đổi tầm nhìn (bấm
// sang cửa sổ bên cạnh rồi bấm lại) thì tab vẫn hiện suốt, dòng SSE vẫn mở —
// dữ liệu đang mới, không cần làm mới. Ở đây chỉ còn lỗ 1: VÀO màn.
//
// KHÔNG dùng cho màn nhập liệu. `router.refresh()` vẽ lại server component;
// state trong form thì giữ nguyên, nhưng đây là màn ĐỌC nên không cần bàn tới
// chuyện đó — dán nó lên một form đang gõ dở là tự chuốc lấy phiền.

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function LiveBoardSync() {
  const router = useRouter();

  useEffect(() => {
    // Vào màn: bỏ qua bản đệm, lấy bản mới.
    const t = setTimeout(() => router.refresh(), 0);
    return () => clearTimeout(t);
  }, [router]);

  return null;
}
