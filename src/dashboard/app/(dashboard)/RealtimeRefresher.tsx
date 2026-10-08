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
// TAB KHÔNG AI NHÌN THÌ KHÔNG GIỮ KẾT NỐI (21/08/2026).
//
// Đây là chỗ chữa cái "đơ 5–10 phút, bấm nút không ăn" mà người dùng báo. Mỗi
// EventSource là một kết nối HTTP/1.1 không bao giờ đóng, mà trình duyệt chỉ
// cho 6 kết nối tới một origin — nên mỗi tab mở nuốt vĩnh viễn một chỗ. Đo trên
// staging: 1 tab còn 5 chỗ, 4 tab còn 2, tới tab thứ SÁU là hết sạch, trang
// không tải nổi (treo 300 giây) trong lúc CPU máy chủ 0.03%. Phòng khám mở
// khoảng mười tab.
//
// Nay dòng chỉ sống trong lúc tab đang hiện, và tab đang ẩn cũng không dựng lại
// trang. Mười tab mở mà một tab đang nhìn thì hệ thống dùng MỘT kết nối, còn
// năm chỗ trống. Luật nằm ở `lib/nhip-lam-moi`, tách khỏi React để test được —
// file này chỉ còn nối chúng với API trình duyệt.
//
// Vì sao KHÔNG bầu một "tab chủ" giữ dòng chung: `navigator.locks` chỉ có trong
// secure context, mà staging lẫn prod đều là HTTP thường trên một địa chỉ IP —
// đo tại chỗ 21/08, `isSecureContext` là false. Chi tiết ở `lib/nhip-lam-moi`.
//
// Bật HTTP/2 (cần HTTPS + tên miền) sẽ xoá hẳn giới hạn 6 kết nối. Chuyện đó
// KHÔNG làm phần này thừa: nó cắt việc thừa, không chỉ né một giới hạn.

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { SU_KIEN_DOI_CA } from "./dung-doi-ca";
import {
  AN_HAN_ROT_MS,
  moDongTheoHien,
  SU_KIEN_BANG,
  taoNhipLamMoi,
  trangThaiDong,
} from "../../lib/nhip-lam-moi";
import { nhipKhiHien, taoGopBatKip } from "../../lib/nhip-khi-hien";

// Lưới an toàn cho lúc dòng sự kiện rớt. EventSource tự nối lại (trình duyệt
// lo), nên nhịp này chỉ để phòng trường hợp cả dòng lẫn lần nối lại đều hỏng —
// và 25s ở bản cũ là quá dày cho việc đó: nó tự nó là nguồn tải đều đặn lớn
// nhất của hệ thống.
//
// Nhịp này chỉ chạy ở tab ĐANG HIỆN: `nhan()` bỏ lượt khi tab ẩn, mà tab ẩn thì
// cũng chẳng có dòng nào để mà rớt.
const POLL_MS = 60_000;

// Các bảng màn nghe tức thời. Mỗi bảng phải có trigger `trg_notify_<bảng>` gọi
// `notify_row_change` (pg_notify → FastAPI SSE; mẫu 20260806000001) — thêm bảng
// ở đây mà thiếu trigger thì danh sách im lặng vô dụng.
const LIVE_TABLES = [
  "appointment",
  "visit",
  "work_item",
  "work_item_event",
  "payment",
  "lab_result",
  "service_log",
  "prescription",
  "encounter_flow",
  "vital_measurement",
  "consultation",
  "consultation_note",
  "service_order",
  "queue_entry",
  "review_round",
  "round_requirement",
  "clinical_record",
  "patient_medical_profile",
  // Chỉ định thư ký nhập chờ bác sĩ duyệt — màn bác sĩ phải thấy ngay.
  "service_order_draft",
  "cskh_action",
  "staff_task",
  "work_roster",
  // BỐN BẢNG CỦA MÀN CHĂM SÓC (08/08/2026). Thiếu chúng ở đây thì hai CSKH
  // ngồi cạnh nhau không thấy việc của nhau: người này ghi xong cuộc gọi, màn
  // người kia vẫn sáng "Làm bước này" — và khách nghe máy hai lần trong một
  // buổi, đúng thứ chuỗi bước sinh ra để chống. Trigger: 20260814000001.
  "tuong_tac_cskh",
  "tep_ket_qua",
  "phan_hoi_khach",
  "hen_goi_lai",
  // Lát 4 bản giao diện mẫu (26/09/2026): phiếu kết quả đổi trạng thái (phòng
  // nhập xong → bàn bác sĩ thấy) và dòng hành trình người đưa tin ghi SAU giao
  // dịch gốc. Trigger ở 20260926000007 — form_instance chỉ báo khi đổi trạng thái.
  "form_instance",
  "luot_dong_thoi_gian",
  // Sổ sửa / bỏ chỉ định (Khối 2, 06/10/2026) — trigger ở 20261006200000.
  "so_sua_chi_dinh",
  // Liệu trình điều trị nhiều buổi (08/10/2026) — trigger ở 20261008100000.
  "lieu_trinh",
  "lieu_trinh_lich_su",
  "lieu_trinh_buoi",
  // CỐ Ý KHÔNG CÓ `thong_bao` (27/09/2026): chuông tự hỏi lại danh sách của nó
  // qua `useNgheBang` — dựng lại cả trang cho mỗi cuộc gọi của trưởng ca là
  // việc thừa. Cùng lý do `slot_hold` không nằm đây.
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

    // QUAY LẠI TAB = MỘT LẦN BẮT KỊP, tối đa một lần mỗi 2 giây (30/09/2026).
    // Người lướt A → B → A trong một giây làm A hiện lại hai lần; lần sau được
    // HOÃN tới cuối cửa sổ chứ không vứt — quãng mù dù ngắn vẫn phải bắt kịp.
    const batKip = taoGopBatKip({
      viec: () => {
        nhip.batKip();
        chuongCa.batKip();
        // Màn tự fetch (chuông, trưởng ca, check-out…) cũng mù suốt quãng ẩn,
        // và router.refresh() không với tới state của chúng. `null` = "không
        // rõ bảng nào đổi" — mọi người nghe SU_KIEN_BANG đều coi là phải hỏi lại.
        window.dispatchEvent(new CustomEvent(SU_KIEN_BANG, { detail: null }));
      },
      dangAn,
      bayGio: () => Date.now(),
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
    // `tables` cho một trang thu hẹp lại chỉ những bảng nó vẽ.
    const wanted = new Set(tables);

    const goDong = moDongTheoHien({
      moDong: (nhanTin) => {
        const es = new EventSource("/api/events/stream");
        // TÌNH TRẠNG DÒNG cho các chỉ báo (xem `trangThaiDong`). Lỗi chưa báo
        // ngay: EventSource tự nối lại sau vài giây, và một lần chớp không
        // đáng một dòng chữ vàng "mất kết nối".
        let henRot: ReturnType<typeof setTimeout> | undefined;
        trangThaiDong.dat("dang-noi");
        es.addEventListener("open", () => {
          clearTimeout(henRot);
          henRot = undefined;
          trangThaiDong.dat("song");
        });
        es.addEventListener("error", () => {
          if (henRot !== undefined) return;
          henRot = setTimeout(() => trangThaiDong.dat("rot"), AN_HAN_ROT_MS);
        });
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
        return () => {
          clearTimeout(henRot);
          es.close();
          trangThaiDong.dat("dang-noi");
        };
      },

      dangAn,
      ngheDoiHien: (fn) => {
        document.addEventListener("visibilitychange", fn);
        return () => document.removeEventListener("visibilitychange", fn);
      },

      xuLy: (t) => {
        if (t === null || wanted.has(t)) nhip.nhan();
        if (t === "work_roster") chuongCa.nhan();
        // Phát tiếp cho các màn muốn tự xử lý một bảng cụ thể mà KHÔNG dựng lại
        // cả trang (màn Đặt lịch nghe `slot_hold`). Trước đây mỗi màn như vậy
        // tự mở EventSource riêng — tức thêm một kết nối bị giữ vĩnh viễn.
        window.dispatchEvent(new CustomEvent(SU_KIEN_BANG, { detail: t }));
      },

      // QUÃNG ẨN LÀ QUÃNG MÙ. Dòng đã đóng suốt lúc tab ẩn, nên không cách nào
      // biết đã bỏ lỡ gì — mở lại là làm mới một lượt, không hỏi.
      //
      // MỘT tay nghe `visibilitychange` duy nhất, do `moDongTheoHien` giữ. Hai
      // tay nghe riêng sẽ phụ thuộc vào thứ tự đăng ký để không dựng trang hai
      // lượt, và đó là loại phụ thuộc không ai thấy khi đọc. Từ 30/09/2026
      // `LiveBoardSync` cũng thôi nghe `visibilitychange`/`focus` — quay lại tab
      // chỉ còn lần bắt kịp này.
      khiMoLai: () => batKip.xin(),
    });

    // Tab ẩn thì huỷ hẳn nhịp; hiện lại thì `batKip` ở trên đã làm mới rồi.
    const goPoll = nhipKhiHien(() => nhip.nhan(), POLL_MS, { hoiKhiHien: false });

    return () => {
      goPoll();
      goDong();
      batKip.dung();
      nhip.dung();
      chuongCa.dung();
    };
  }, [router, tables]);

  return null;
}
