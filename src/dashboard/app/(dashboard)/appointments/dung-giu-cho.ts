"use client";

// CHỖ NGƯỜI KHÁC ĐANG GIỮ — một nguồn cho mọi màn đặt lịch.
//
// Trước 16/09/2026 khối này nằm trong BookingHub, và chỉ chạy cho NGÀY ĐANG
// XEM. Popup khung giờ của bảng Bác sĩ × tuần mở được một ngày khác, nên nó
// không có cách nào biết ai đang giữ chỗ — hai CSKH tranh một khung chỉ biết
// khi trigger trả 409. Tách thành hook để popup gọi theo ngày CỦA NÓ.
//
// Máy chủ đã bỏ chỗ do chính người đang xem giữ (slot_hold_service.active):
// tô "đang giữ" lên ô mình vừa bấm là tự nói với mình rằng có người tranh chỗ.

import { useEffect, useState } from "react";

import { fmtTime, VN_TZ } from "@/lib/datetime";
import { SU_KIEN_BANG } from "../../../lib/nhip-lam-moi";

/** Một chỗ đang được người khác giữ — trả từ /api/appointments/slot-hold. */
interface SlotHoldLite {
  doctor_id: string | null;
  slot_start: string;
  held_by_name: string | null;
}

/** Khoá của một ô: "docId|ngày|giờ" (giờ VN, "HH:mm"). */
export function khoaGiuCho(
  doctorId: string | null,
  isoDate: string,
  time: string,
): string {
  return `${doctorId ?? ""}|${isoDate}|${time}`;
}

/** Bản đồ chỗ người khác đang giữ trong `date`. Giá trị là tên người giữ —
 *  màn hiện KHÔNG hiện tên (Tuyền 16/09/2026), chỉ đổi màu ô; giữ lại vì nhật
 *  ký và vì hiện tên là một dòng, còn lấy lại được tên thì không.
 *
 *  `date` rỗng/null = không hỏi gì, trả bản đồ rỗng. */
export function useGiuCho(date: string | null): Map<string, string> {
  const [giu, setGiu] = useState<Map<string, string>>(new Map());

  useEffect(() => {
    if (!date) return;
    let alive = true;
    const load = () =>
      fetch(`/api/appointments/slot-hold?date=${date}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((d: { items?: SlotHoldLite[] } | null) => {
          if (!alive || !d?.items) return;
          const m = new Map<string, string>();
          for (const h of d.items) {
            const dt = new Date(h.slot_start);
            if (Number.isNaN(dt.getTime())) continue;
            const isoDate = dt.toLocaleDateString("en-CA", { timeZone: VN_TZ });
            m.set(
              khoaGiuCho(h.doctor_id, isoDate, fmtTime(dt)),
              h.held_by_name ?? "người khác",
            );
          }
          setGiu(m);
        })
        .catch(() => {
          // Đọc không được thì giữ bản đồ cũ. Xoá sạch nghĩa là mọi ô đột ngột
          // hiện "còn trống" — đúng câu khẳng định gây đặt trùng.
        });
    const t = setTimeout(load, 0);
    // NHỊP 5 GIÂY — trước 14/08/2026 là 15s.
    //
    // Đo trên staging: máy chủ thấy một chỗ giữ mới sau 27–40ms, nên gần như
    // TOÀN BỘ độ trễ người bên cạnh cảm nhận chính là nhịp này. 15s nghĩa là
    // trung bình 8 giây, chậm nhất 16 — trong khi hai CSKH tranh một khung
    // thường quyết trong vòng vài giây, tức là cảnh báo tới sau khi việc đã rồi.
    //
    // Giá phải trả đã ĐO, không ước lượng: một nhịp tốn 4,8ms cả chuỗi (GoTrue
    // xác minh token 2,1ms + FastAPI đọc bảng 2,7ms — xem scripts/tests/
    // do-nhip-hoi.py). Bốn CSKH cùng mở màn ở nhịp 5s = 0,8 lượt/giây = 0,4%
    // một lõi. Ngưỡng đáng xem lại: khoảng 30 người cùng mở màn này.
    //
    // TAB ẨN THÌ BỎ NHỊP (21/08/2026). Bản đồ chỗ giữ chỉ có nghĩa khi có người
    // nhìn lưới. Một tab ẩn hỏi lại mỗi 5 giây là mỗi 5 giây chiếm một trong
    // sáu kết nối HTTP/1.1 mà trình duyệt cho phép tới origin này — đúng thứ
    // đang khan hiếm (xem `lib/nhip-lam-moi`). Quay lại thì đã có tay nghe
    // `visibilitychange` ngay dưới đây hỏi lại tức thì, nên không mù chỗ nào.
    const iv = setInterval(() => {
      if (document.visibilityState === "hidden") return;
      void load();
    }, 5000);

    // TAB BỊ CHE THÌ HỎI LẠI NGAY KHI QUAY LẠI.
    //
    // Trình duyệt bóp nhịp của tab bị ẩn, nên quay lại sau mười phút thì bản đồ
    // chỗ giữ đang cũ và phải chờ hết một nhịp mới đúng. Ở nhịp 15s chuyện đó
    // đã khó chịu; nhưng lý do thật để thêm bây giờ là: hạ nhịp chỉ có nghĩa
    // nếu lúc người ta THỰC SỰ NHÌN màn hình thì dữ liệu là mới.
    const khiHien = () => {
      if (document.visibilityState === "visible") void load();
    };
    document.addEventListener("visibilitychange", khiHien);

    // TIN ĐẨY: AI ĐÓ VỪA GIỮ HOẶC THẢ MỘT CHỖ.
    //
    // Tuyền 14/08/2026: *"mỗi vị trí lịch nào mà người này click thì cũng sẽ
    // hiện realtime trên màn hình của người kia, cả 8 CSKH cùng làm cũng thế"*.
    //
    // Nhịp 5 giây cho ra ~2,5 giây trung bình. Với tin đẩy thì còn đúng một
    // vòng mạng: `slot_hold` có trigger `pg_notify` từ 14/08 (migration
    // 20260814000001), FastAPI nghe rồi đẩy SSE về đây.
    //
    // MÀN NÀY KHÔNG DỰNG LẠI CẢ TRANG, chỉ hỏi lại một endpoint nhẹ (4,8ms cả
    // chuỗi). `RealtimeRefresher` gọi `router.refresh()` cho mọi tin — dựng lại
    // toàn bộ cây server component; tám CSKH bấm lướt qua các khung giờ sẽ
    // thành một trận mưa render trên mọi tab đang mở, cho một thay đổi mà chỉ
    // màn này quan tâm.
    //
    // NHƯNG KHÔNG CÒN TỰ MỞ DÒNG RIÊNG (21/08/2026). Trước đây chỗ này mở
    // EventSource thứ hai, nên một tab ở màn Đặt lịch nuốt HAI trong sáu kết
    // nối HTTP/1.1 của trình duyệt thay vì một — phòng khám chạm trần chỉ sau
    // ba tab, và trần đó là lúc trang không tải nổi nữa (đo 21/08, xem
    // `lib/nhip-lam-moi`). Nay nghe ké dòng chung do một tab giữ; điều muốn giữ
    // — tự quyết làm gì với tin, không bị ép dựng lại trang — vẫn nguyên.
    //
    // GIỮ NHỊP 5 GIÂY LÀM LƯỚI AN TOÀN. Dòng SSE có thể rớt, và ở đúng màn này
    // thì im lặng là thứ tệ nhất: người trực tin rằng khung còn trống.
    const khiBangDoi = (ev: Event) => {
      const bang = (ev as CustomEvent<string | null>).detail;
      // `null` = tin méo hoặc không rõ bảng nào. Cứ hỏi lại — một lượt gọi
      // 4,8ms rẻ hơn nhiều so với việc bỏ sót một chỗ vừa bị giữ.
      if (bang === "slot_hold" || bang === null) void load();
    };
    window.addEventListener(SU_KIEN_BANG, khiBangDoi);

    return () => {
      alive = false;
      clearTimeout(t);
      clearInterval(iv);
      document.removeEventListener("visibilitychange", khiHien);
      window.removeEventListener(SU_KIEN_BANG, khiBangDoi);
    };
  }, [date]);

  // Đóng popup KHÔNG xoá bản đồ (xoá ở đây là setState trong effect). Không cần:
  // khoá có mang ngày, nên dữ liệu cũ của ngày khác không khớp ô nào; mở lại
  // đúng ngày ấy thì `load()` chạy ngay lượt đầu, chậm nhất là dữ liệu 5 giây.
  return date ? giu : RONG;
}

const RONG: Map<string, string> = new Map();
