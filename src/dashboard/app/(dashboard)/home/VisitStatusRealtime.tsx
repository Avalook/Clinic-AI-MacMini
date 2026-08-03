"use client";

// Chỉ báo "đang cập nhật liên tục" cho bảng trạng thái buổi khám của Lễ tân.
//
// CHỈ CÒN LÀ CHỈ BÁO. Trước đây component này tự subscribe visit/appointment/
// payment, tự debounce 1500ms rồi tự gọi router.refresh(), CỘNG một
// setInterval 30 giây — trong khi RealtimeRefresher ở layout đã nghe đúng ba
// bảng đó và cũng đang gọi router.refresh() theo nhịp riêng.
//
// Hai bộ làm mới độc lập trên cùng một trang không "an toàn gấp đôi": mỗi lần
// một trong hai kích hoạt, TOÀN BỘ cây server component của trang chủ chạy lại
// (11 truy vấn Supabase). Với hai poll lệch pha 25s và 30s, trang chủ tự nạp
// lại khoảng năm lần mỗi phút khi không ai chạm vào máy — và mỗi sự kiện
// realtime thì render lại hai lần.
//
// Việc làm mới giờ thuộc về đúng một chỗ (RealtimeRefresher). Ở đây còn lại thứ
// mà chỗ kia không làm được: nói cho Lễ tân biết kênh còn sống, vì một bảng
// đứng im vì "không có gì đổi" và một bảng đứng im vì "mất kết nối" trông giống
// hệt nhau.

import { useEffect, useState } from "react";
import { getSupabaseBrowser } from "../../../lib/supabase-browser";

type Health = "connecting" | "live" | "down";

export default function VisitStatusRealtime() {
  const [health, setHealth] = useState<Health>("connecting");

  useEffect(() => {
    const supabase = getSupabaseBrowser();
    // Kênh rỗng, không đăng ký bảng nào: chỉ để đọc trạng thái websocket. Đăng
    // ký thêm bảng ở đây là quay lại đúng chỗ vừa gỡ bỏ.
    const channel = supabase.channel("visit-status-heartbeat").subscribe((status) => {
      if (status === "SUBSCRIBED") setHealth("live");
      else if (status === "CHANNEL_ERROR" || status === "TIMED_OUT") setHealth("down");
      else if (status === "CLOSED") setHealth("connecting");
    });
    return () => {
      void supabase.removeChannel(channel);
    };
  }, []);

  if (health === "down") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-warning">
        <span className="inline-flex h-1.5 w-1.5 rounded-full bg-warning" />
        Mất kết nối cập nhật — bảng có thể đang cũ
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-ink-muted">
      <span
        className={`inline-flex h-1.5 w-1.5 rounded-full motion-reduce:animate-none ${
          health === "live" ? "animate-pulse bg-green-500" : "bg-ink-faint"
        }`}
      />
      {health === "live" ? "Cập nhật liên tục" : "Đang kết nối…"}
    </span>
  );
}
