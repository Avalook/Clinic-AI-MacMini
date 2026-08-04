"use client";

// Chỉ báo kênh realtime cho màn /appointments.
//
// HAI LÝ DO NÓ KHÔNG CÒN TỰ LÀM MỚI, VÀ MỘT LÝ DO NÓ CHƯA TỪNG ĐẾM ĐÚNG.
//
// 1. RealtimeRefresher ở layout đã nghe bảng `appointment` và đã gọi
//    router.refresh(). Giữ thêm một bộ ở đây nghĩa là mỗi thay đổi lịch hẹn
//    render lại toàn trang hai lần, lệch nhau vài trăm mili-giây.
//
// 2. Con số "+N cập nhật" ở bản cũ đếm sự kiện postgres_changes trên bảng
//    `appointment` — một bảng CHƯA từng nằm trong publication supabase_realtime
//    (chỉ work_item/work_item_event được thêm ở 20260803000003). Subscribe một
//    bảng chưa publish không báo lỗi, chỉ im lặng, nên bộ đếm này luôn bằng 0 và
//    cái chấm xanh "Realtime" nhấp nháy cạnh nó suốt nhiều tháng mà không nối
//    với sự thật nào. 20260803000004 đã publish bảng này.
//
// Thứ còn lại ở đây là thứ RealtimeRefresher không nói được vì nó render null:
// kênh còn sống hay đã rớt. Một lưới lịch đứng im vì hôm nay chưa ai đặt gì và
// một lưới đứng im vì websocket chết trông hoàn toàn giống nhau, mà chỉ một
// trong hai là an toàn để đặt tiếp.

import { useEffect, useState } from "react";
import { getSupabaseBrowser } from "../../../lib/supabase-browser";

type Health = "connecting" | "live" | "down";

export default function AppointmentsRealtime() {
  const [health, setHealth] = useState<Health>("connecting");

  useEffect(() => {
    const supabase = getSupabaseBrowser();
    const channel = supabase
      .channel("appointments-heartbeat")
      .subscribe((status) => {
        if (status === "SUBSCRIBED") setHealth("live");
        else if (status === "CHANNEL_ERROR" || status === "TIMED_OUT")
          setHealth("down");
        else if (status === "CLOSED") setHealth("connecting");
      });
    return () => {
      void supabase.removeChannel(channel);
    };
  }, []);

  if (health === "down") {
    return (
      <div className="flex items-center gap-2 text-xs text-warning">
        <span className="inline-flex h-1.5 w-1.5 rounded-full bg-warning" />
        <span>Mất kết nối — lưới có thể đang cũ, tải lại trước khi đặt</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-xs">
      <span
        className={`inline-flex h-1.5 w-1.5 rounded-full motion-reduce:animate-none ${
          health === "live"
            ? "animate-pulse bg-status-completed"
            : "bg-ink-faint"
        }`}
      />
      <span className="text-ink-muted">
        {health === "live" ? "Realtime" : "Đang kết nối…"}
      </span>
    </div>
  );
}
