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

    // Nhìn lại màn sau khi đi đâu đó.
    const onVisible = () => {
      if (document.visibilityState === "visible") router.refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);

    return () => {
      clearTimeout(t);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [router]);

  return null;
}
