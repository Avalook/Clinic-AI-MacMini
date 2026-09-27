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

import type { TrangThaiDong } from "../../../lib/nhip-lam-moi";
import { useTrangThaiDong } from "../dung-nghe-bang";

type Health = "connecting" | "live" | "down";

const THEO_TRANG_THAI = {
  "dang-noi": "connecting",
  song: "live",
  rot: "down",
} as const satisfies Record<TrangThaiDong, Health>;

export default function VisitStatusRealtime() {
  // ĐỌC ĐÚNG DÒNG ĐANG CHỞ TIN (27/09/2026). Bản trước mở một kênh rỗng của
  // Supabase Realtime chỉ để đọc tình trạng websocket — một kết nối KHÔNG chở
  // tin nào của hệ thống (tin đi LISTEN/NOTIFY → SSE từ 06/08). Chấm xanh khi
  // ấy có thể sáng trong lúc dòng SSE đã chết. Nay đọc tình trạng dòng SSE mà
  // RealtimeRefresher giữ — không mở thêm kết nối nào.
  const health: Health = THEO_TRANG_THAI[useTrangThaiDong()];

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
