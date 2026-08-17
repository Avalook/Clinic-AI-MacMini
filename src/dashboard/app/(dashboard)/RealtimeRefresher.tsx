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
// ĐỔI NGUỒN TIN 06/08/2026: KHÔNG CÒN QUA SUPABASE REALTIME.
//
// Realtime đọc nhật ký WAL qua một replication slot, và tạo slot cần quyền
// REPLICATION — thứ database cho thuê không cấp (đo trên Viettel IDC 06/08;
// AWS RDS và Azure cũng vậy). Nay dùng LISTEN/NOTIFY, là SQL thường không đòi
// quyền nào: trigger bắn pg_notify lúc COMMIT, FastAPI nghe rồi đẩy SSE về đây.
//
// ĐỘ TRỄ. Đường cũ đi ba chặng (ghi → WAL → dịch vụ Realtime giải mã →
// websocket). Đường này đi một (ghi → NOTIFY → SSE) — thứ đang ghi dữ liệu
// chính là thứ biết có gì đổi. Còn lại vẫn là debounce 250ms + một lượt render
// server component (≈150–400ms tuỳ trang). Muốn 0ms cho CHÍNH người vừa bấm thì
// vẫn phải cập nhật lạc quan tại chỗ bấm — xem router.refresh() trong
// BookingHub.handleConfirmBooking — chứ không phải chờ tin quay về.

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

import { SU_KIEN_DOI_CA } from "./dung-doi-ca";

// 250ms: đủ để gộp một chuỗi thay đổi của cùng một thao tác (mở lượt khám đụng
// vài bảng) thành một lần render, đủ ngắn để người dùng không kịp thấy độ trễ.
// 1200ms ở bản cũ là hơn một giây thuần chờ trên MỌI cập nhật.
const DEBOUNCE_MS = 250;

// Lưới an toàn cho lúc dòng sự kiện rớt. EventSource tự nối lại (trình duyệt
// lo), nên nhịp này chỉ để phòng trường hợp cả dòng lẫn lần nối lại đều hỏng —
// và 25s ở bản cũ là quá dày cho việc đó: nó tự nó là nguồn tải đều đặn lớn
// nhất của hệ thống.
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
  // BỐN BẢNG CỦA MÀN CHĂM SÓC (08/08/2026). Thiếu chúng ở đây thì hai CSKH
  // ngồi cạnh nhau không thấy việc của nhau: người này ghi xong cuộc gọi, màn
  // người kia vẫn sáng "Làm bước này" — và khách nghe máy hai lần trong một
  // buổi, đúng thứ chuỗi bước sinh ra để chống.
  //
  // Nghe thôi CHƯA ĐỦ: bảng còn phải nằm trong publication `supabase_realtime`
  // (migration 20260809000009), nếu không Postgres không phát gì cả và danh
  // sách này im lặng vô dụng.
  "tuong_tac_cskh",
  "tep_ket_qua",
  "phan_hoi_khach",
  "hen_goi_lai",
] as const;

// PROP `clinicId` ĐÃ BỎ (06/08/2026). Nó từng dùng để bảo Supabase Realtime
// lọc theo phòng khám. Nay máy chủ tự lọc — nó biết người mở dòng thuộc phòng
// khám nào từ chính token, và đó là chỗ DUY NHẤT lọc được an toàn: một giá trị
// do trình duyệt gửi lên thì không phải là cái lọc, chỉ là một lời khai.
//
// Giữ lại một prop không còn tác dụng sẽ khiến người đọc sau tin rằng có một
// lớp lọc ở đây, và tin sai theo hướng nguy hiểm.
export default function RealtimeRefresher({
  tables = LIVE_TABLES as readonly string[],
}: {
  tables?: readonly string[];
}) {
  const router = useRouter();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const chuongCa = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const bump = () => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => router.refresh(), DEBOUNCE_MS);
    };
    // CHUÔNG CA TRỰC — cho dữ liệu client-fetch mà router.refresh không với
    // tới (hai lưới đặt chỗ). Debounce riêng: "áp dụng lịch cả tuần" bắn một
    // tràng notify, và một tràng chuông là một tràng refetch quote vô ích.
    const rungChuongCa = () => {
      if (chuongCa.current) clearTimeout(chuongCa.current);
      chuongCa.current = setTimeout(
        () => window.dispatchEvent(new CustomEvent(SU_KIEN_DOI_CA)),
        DEBOUNCE_MS,
      );
    };

    // LỌC BẢNG Ở ĐÂY, LỌC PHÒNG KHÁM Ở MÁY CHỦ.
    //
    // Phòng khám thì máy chủ lọc: nó biết người mở dòng này thuộc phòng khám
    // nào (từ token), nên tin của phòng khám khác không bao giờ rời máy chủ.
    // Đó là chỗ duy nhất lọc được an toàn — trình duyệt tự khai mình thuộc đâu
    // thì không tính là một cái lọc.
    //
    // Bảng thì lọc ở đây, vì danh sách bảng là chuyện của từng màn: prop
    // `tables` cho một trang thu hẹp lại chỉ những bảng nó vẽ.
    const wanted = new Set(tables);
    const es = new EventSource("/api/events/stream");
    es.addEventListener("change", (ev) => {
      try {
        const { t } = JSON.parse((ev as MessageEvent<string>).data) as {
          t?: string;
        };
        if (!t || wanted.has(t)) bump();
        if (t === "work_roster") rungChuongCa();
      } catch {
        // Tin méo thì cứ làm mới — thà thừa một lượt render còn hơn bỏ sót một
        // thay đổi và để người dùng nhìn dữ liệu cũ.
        bump();
      }
    });
    // KHÔNG tự nối lại ở đây: EventSource đã tự làm, và viết thêm một vòng nối
    // lại của mình sẽ chạy song song với vòng của trình duyệt.

    const poll = setInterval(() => router.refresh(), POLL_MS);

    return () => {
      if (timer.current) clearTimeout(timer.current);
      clearInterval(poll);
      es.close();
    };
  }, [router, tables]);

  return null;
}
