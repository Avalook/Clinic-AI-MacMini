"use client";

// Realtime TOÀN APP — gắn một lần ở (dashboard)/layout.
//
// MỘT KÊNH, MỘT NHỊP, MỘT NGUỒN LÀM MỚI.
//
// Trước đây có bốn thứ cùng gọi router.refresh() trên một trang: file này (poll
// 25s + 20 bảng), VisitStatusRealtime (poll 30s + 3 bảng), AppointmentsRealtime
// (bảng appointment), và NotificationContext. Mỗi lần refresh chạy lại TOÀN BỘ
// cây server component — trang chủ là 11 truy vấn Supabase cộng getCurrentStaff.
// Một tab để yên vẫn gõ vào Supabase khoảng ba mươi truy vấn mỗi 25 giây, nhân
// với số nhân viên đang mở máy. Đó là phần lớn cảm giác "hệ thống chậm".
//
// VÀ NÓ CHƯA TỪNG THẬT SỰ LÀ REALTIME. Danh sách 20 bảng ở bản cũ subscribe vào
// những bảng KHÔNG nằm trong publication `supabase_realtime` (chỉ work_item và
// work_item_event được thêm, ở 20260803000003). Subscribe một bảng chưa publish
// không báo lỗi — nó chỉ im lặng không bao giờ bắn sự kiện. Nên thứ đồng bộ dữ
// liệu suốt thời gian qua là setInterval, còn "realtime" là cái tên.
//
// 20260803000004 publish đúng những bảng có màn vẽ live. Danh sách dưới đây
// PHẢI khớp với migration đó: subscribe thừa thì im lặng vô dụng, publish thừa
// thì Realtime phải chạy RLS cho từng subscriber trên từng thay đổi.
//
// ĐỘ TRỄ THỰC TẾ. Từ lúc Postgres commit tới lúc màn hình đổi: WAL → Realtime →
// websocket (≈40–120ms từ VN tới Supabase Seoul) + debounce 250ms + một lượt
// render lại server component (≈150–400ms tuỳ trang). Tức khoảng 0,5–1 giây, và
// phần lớn nằm ở hai chặng mạng không thể bỏ. Muốn 0ms cho CHÍNH người vừa bấm
// thì phải cập nhật lạc quan ngay tại chỗ bấm — xem router.refresh() trong
// BookingHub.handleConfirmBooking — chứ không phải chờ vòng realtime quay về.

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowser } from "../../lib/supabase-browser";

// 250ms: đủ để gộp một chuỗi thay đổi của cùng một thao tác (mở lượt khám đụng
// vài bảng) thành một lần render, đủ ngắn để người dùng không kịp thấy độ trễ.
// 1200ms ở bản cũ là hơn một giây thuần chờ trên MỌI cập nhật.
const DEBOUNCE_MS = 250;

// Lưới an toàn cho lúc websocket rớt. Realtime bây giờ chạy thật nên nhịp này
// không còn là đường đồng bộ chính, và 25s là quá dày cho một việc chỉ dùng khi
// mạng hỏng: nó tự nó đã là nguồn tải đều đặn lớn nhất của hệ thống.
const POLL_MS = 60_000;

// Các bảng ĐANG được publish (20260803000004). Đổi ở đây thì phải đổi cả ở
// migration — một danh sách lệch nhau là cách "realtime" chết trong im lặng.
const LIVE_TABLES = [
  "appointment",
  "visit",
  "work_item",
  "work_item_event",
  "payment",
  "lab_result",
  "service_log",
  "prescription",
  "cskh_action",
  "staff_task",
  "work_roster",
] as const;

export default function RealtimeRefresher({
  tables = LIVE_TABLES as readonly string[],
  clinicId = null,
}: {
  tables?: readonly string[];
  /** Lọc phía server theo phòng khám đang đăng nhập. */
  clinicId?: string | null;
}) {
  const router = useRouter();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const supabase = getSupabaseBrowser();
    const bump = () => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => router.refresh(), DEBOUNCE_MS);
    };

    let channel = supabase.channel("global-realtime-refresh");
    for (const table of tables) {
      channel = channel.on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table,
          // Lọc NGAY TẠI SERVER. Không có nó, một thay đổi ở phòng khám khác vẫn
          // được đẩy tới trình duyệt này rồi bị RLS chặn — đã tốn chặng mạng, và
          // với `event: "*"` thì mỗi lần như vậy vẫn kích hoạt một lượt render
          // lại toàn trang cho một dữ liệu người này không được xem.
          ...(clinicId ? { filter: `clinic_id=eq.${clinicId}` } : {}),
        },
        bump,
      );
    }
    channel.subscribe();

    const poll = setInterval(() => router.refresh(), POLL_MS);

    return () => {
      if (timer.current) clearTimeout(timer.current);
      clearInterval(poll);
      void supabase.removeChannel(channel);
    };
  }, [router, tables, clinicId]);

  return null;
}
