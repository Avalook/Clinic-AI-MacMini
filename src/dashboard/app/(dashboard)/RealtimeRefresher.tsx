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
//
// MỘT DÒNG CHO CẢ TRÌNH DUYỆT, KHÔNG PHẢI MỘT DÒNG CHO MỖI TAB (21/08/2026).
//
// Đây là chỗ chữa cái "đơ 5–10 phút, bấm nút không ăn" mà người dùng báo. Mỗi
// EventSource là một kết nối HTTP/1.1 không bao giờ đóng, mà trình duyệt chỉ
// cho 6 kết nối tới một origin — nên mỗi tab mở nuốt vĩnh viễn một chỗ. Đo trên
// staging: 1 tab còn 5 chỗ, 4 tab còn 2, tới tab thứ SÁU là hết sạch, trang
// không tải nổi (treo 300 giây) trong lúc CPU máy chủ 0.03%. Phòng khám mở
// khoảng mười tab.
//
// Nay chỉ MỘT tab giữ dòng (bầu bằng navigator.locks) rồi phát lại cho các tab
// khác qua BroadcastChannel; và tab đang ẩn thì không dựng lại trang, chỉ ghi
// nợ rồi trả lúc người ta quay lại nhìn. Cả hai luật nằm ở `lib/nhip-lam-moi`,
// tách khỏi React để test được — file này chỉ còn nối chúng với API trình duyệt.
//
// Bật HTTP/2 (cần HTTPS + tên miền) sẽ xoá hẳn giới hạn 6 kết nối. Chuyện đó
// KHÔNG làm phần này thừa: nó cắt việc thừa, không chỉ né một giới hạn.

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { SU_KIEN_DOI_CA } from "./dung-doi-ca";
import {
  moDongSuKien,
  SU_KIEN_BANG,
  taoNhipLamMoi,
  type Go,
  type Kenh,
} from "../../lib/nhip-lam-moi";

// Lưới an toàn cho lúc dòng sự kiện rớt. EventSource tự nối lại (trình duyệt
// lo), nên nhịp này chỉ để phòng trường hợp cả dòng lẫn lần nối lại đều hỏng —
// và 25s ở bản cũ là quá dày cho việc đó: nó tự nó là nguồn tải đều đặn lớn
// nhất của hệ thống.
//
// Nhịp này cũng là lưới cho một bẫy mới: tab chủ có thể là một tab đang ẩn, và
// trình duyệt được phép đóng băng tab nền. Tab người ta ĐANG NHÌN vẫn tự bắt
// kịp trong một nhịp, kể cả khi tab chủ đã ngủ.
const POLL_MS = 60_000;

// Tên khoá bầu tab chủ. Web Locks đã tự giới hạn trong một origin nên không cần
// gắn thêm gì; đổi tên này là chia đôi phòng bầu cử, tức lại hai dòng SSE.
const KHOA_DONG = "clinicai-dong-su-kien";

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

  useEffect(() => {
    const dangAn = () => document.visibilityState === "hidden";

    // Nhịp dựng lại trang.
    const nhip = taoNhipLamMoi({
      lamMoi: () => router.refresh(),
      dangAn,
      hen: (fn, ms) => setTimeout(fn, ms),
      huy: (h) => clearTimeout(h as ReturnType<typeof setTimeout>),
    });

    // CHUÔNG CA TRỰC — cho dữ liệu client-fetch mà router.refresh không với
    // tới (hai lưới đặt chỗ). Nhịp RIÊNG: "áp dụng lịch cả tuần" bắn một tràng
    // notify, và một tràng chuông là một tràng refetch quote vô ích.
    const chuongCa = taoNhipLamMoi({
      lamMoi: () => window.dispatchEvent(new CustomEvent(SU_KIEN_DOI_CA)),
      dangAn,
      hen: (fn, ms) => setTimeout(fn, ms),
      huy: (h) => clearTimeout(h as ReturnType<typeof setTimeout>),
    });

    // LỌC BẢNG Ở ĐÂY, LỌC PHÒNG KHÁM Ở MÁY CHỦ.
    //
    // Phòng khám thì máy chủ lọc: nó biết người mở dòng này thuộc phòng khám
    // nào (từ token), nên tin của phòng khám khác không bao giờ rời máy chủ.
    // Đó là chỗ duy nhất lọc được an toàn — trình duyệt tự khai mình thuộc đâu
    // thì không tính là một cái lọc.
    //
    // Bảng thì lọc ở đây, vì danh sách bảng là chuyện của từng màn: prop
    // `tables` cho một trang thu hẹp lại chỉ những bảng nó vẽ. Tab chủ phát lại
    // tin THÔ, chưa lọc — hai tab có thể đang xem hai màn khác nhau, nên lọc
    // phải ở phía người nhận.
    const wanted = new Set(tables);

    const goDong = moDongSuKien({
      moDong: (nhanTin) => {
        const es = new EventSource("/api/events/stream");
        es.addEventListener("change", (ev) => {
          try {
            const { t } = JSON.parse((ev as MessageEvent<string>).data) as {
              t?: string;
            };
            nhanTin(t ?? null);
          } catch {
            // Tin méo thì cứ làm mới — thà thừa một lượt render còn hơn bỏ sót
            // một thay đổi và để người dùng nhìn dữ liệu cũ.
            nhanTin(null);
          }
        });
        // KHÔNG tự nối lại ở đây: EventSource đã tự làm, và viết thêm một vòng
        // nối lại của mình sẽ chạy song song với vòng của trình duyệt.
        return () => es.close();
      },

      xinLamChu: xinLamChu(),
      moKenh: moKenh(),

      xuLy: (t) => {
        if (t === null || wanted.has(t)) nhip.nhan();
        if (t === "work_roster") chuongCa.nhan();
        // Phát tiếp cho các màn muốn tự xử lý một bảng cụ thể mà KHÔNG dựng lại
        // cả trang (màn Đặt lịch nghe `slot_hold`). Trước đây mỗi màn như vậy
        // tự mở EventSource riêng — tức thêm một kết nối bị giữ vĩnh viễn.
        window.dispatchEvent(new CustomEvent(SU_KIEN_BANG, { detail: t }));
      },
    });

    const quayLai = () => {
      if (dangAn()) return;
      nhip.hienLai();
      chuongCa.hienLai();
    };
    document.addEventListener("visibilitychange", quayLai);

    const poll = setInterval(() => nhip.nhan(), POLL_MS);

    return () => {
      document.removeEventListener("visibilitychange", quayLai);
      clearInterval(poll);
      goDong();
      nhip.dung();
      chuongCa.dung();
    };
  }, [router, tables]);

  return null;
}

/** Bầu tab chủ bằng Web Locks. `null` nếu trình duyệt không có. */
function xinLamChu(): ((duoc: () => void) => Go) | null {
  if (typeof navigator === "undefined" || !navigator.locks) return null;

  return (duoc) => {
    // HAI CÁCH RÚT LUI KHÁC NHAU, và lẫn chúng là để lại một dòng SSE ma.
    // Đang XẾP HÀNG thì rút bằng cách huỷ tín hiệu. Đang GIỮ khoá thì tín hiệu
    // vô tác dụng — Web Locks chỉ nhả khi lời hứa mình đang giữ kết thúc.
    let nha: (() => void) | null = null;
    let daRut = false;
    const ac = new AbortController();

    void navigator.locks
      .request(KHOA_DONG, { signal: ac.signal }, () =>
        new Promise<void>((xong) => {
          // Giành được khoá đúng lúc tab đang đóng: nhả ngay, đừng mở dòng.
          if (daRut) {
            xong();
            return;
          }
          nha = xong;
          duoc();
        }),
      )
      .catch(() => {
        // AbortError khi tab đóng lúc còn xếp hàng — đúng như mong đợi, không
        // phải lỗi.
      });

    return () => {
      daRut = true;
      if (nha) nha();
      else ac.abort();
    };
  };
}

/** Kênh phát lại giữa các tab. `null` nếu trình duyệt không có. */
function moKenh(): ((nhan: (t: string | null) => void) => Kenh) | null {
  if (typeof BroadcastChannel === "undefined") return null;

  return (nhan) => {
    const bc = new BroadcastChannel(KHOA_DONG);
    bc.addEventListener("message", (ev) => {
      const t = (ev as MessageEvent<string | null>).data;
      nhan(typeof t === "string" ? t : null);
    });
    return {
      // BroadcastChannel KHÔNG gửi lại cho chính kênh vừa gửi, nên tab chủ
      // không xử lý tin của mình hai lần.
      gui: (t) => bc.postMessage(t),
      dong: () => bc.close(),
    };
  };
}
