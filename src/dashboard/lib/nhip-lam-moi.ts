// NHỊP LÀM MỚI VÀ DÒNG SỰ KIỆN — phần quyết định, tách khỏi React để test được.
//
// VÌ SAO FILE NÀY RA ĐỜI (đo 21/08/2026 trên staging, trình duyệt thật).
//
// Người dùng báo "đơ 5–10 phút, bấm nút không ăn, bấm năm lần mới ghi nhận", và
// đơ CẢ KHI DÙNG 4G. Giả thuyết ban đầu là bão render: 91 lời gọi
// router.refresh() nhân với số tab đang mở, dồn lên một tiến trình Node.
//
// Đo xong thì nguyên nhân chính là chuyện khác, và nằm hẳn trong TRÌNH DUYỆT.
//
// EventSource là một kết nối HTTP không bao giờ đóng. Trên HTTP/1.1 (chưa có
// TLS nên chưa có HTTP/2) trình duyệt chỉ cho 6 kết nối tới một origin. Mỗi tab
// mở một EventSource, nên mỗi tab NUỐT VĨNH VIỄN một trong sáu chỗ ấy:
//
//     số tab mở   1    2    4    5    6
//     còn lại     5    4    2    1    0
//
// Đo bằng cách bắn 6 request /home cùng lúc rồi đếm số chạy song song — ra đúng
// dãy trên. Tới tab thứ SÁU thì không còn chỗ nào: tab mới không tải nổi trang
// (navigate treo hết 300 giây), và fetch từ tab cũ cũng treo. Đúng lúc đó CPU
// trên máy chủ là dashboard 0.03%, api 0.25%, db 0.39%, load 0.43 — MÁY CHỦ
// RỖNG. Đó là lý do đơ cả trên 4G: nó không xảy ra ở mạng, cũng không ở máy chủ.
//
// Phòng khám mở khoảng mười tab. Nên hệ thống không "chậm" — nó ĐỨNG HẲN, và
// mọi phép đo phía máy chủ đều báo khoẻ trong lúc ấy.
//
// CÁCH CHỮA: TAB NÀO KHÔNG AI NHÌN THÌ KHÔNG GIỮ GÌ CẢ.
//
// Một tab đang ẩn không vẽ gì, nên nó không cần tin tức, và nó cũng không cần
// một kết nối. Đóng dòng lúc ẩn, mở lại lúc hiện, rồi làm mới một lượt để bắt
// kịp. Mười tab mở mà một tab đang nhìn thì hệ thống dùng MỘT kết nối, còn năm
// chỗ trống — thay vì mười tab nuốt sạch sáu chỗ.
//
// ĐÃ CÂN NHẮC VÀ BỎ: bầu một "tab chủ" giữ dòng chung rồi phát lại cho các tab
// khác qua BroadcastChannel. Nó cũng ra một kết nối, nhưng cách bầu duy nhất
// đáng tin là `navigator.locks`, mà Web Locks CHỈ CÓ trong secure context.
// Kiểm trên chính staging 21/08: `window.isSecureContext` là false và
// `typeof navigator.locks` là "undefined" — prod cũng vậy, cả hai đều là HTTP
// thường trên một địa chỉ IP. Nghĩa là bản bầu-tab-chủ sẽ âm thầm rơi về cách
// cũ ĐÚNG Ở HAI CHỖ CẦN NÓ NHẤT, và test vẫn xanh vì test có Web Locks giả.
// Tự viết bầu cử bằng nhịp tim qua BroadcastChannel thì vướng chuyện trình
// duyệt bóp nhịp hẹn giờ của tab nền xuống một lần mỗi phút — tức tab chủ đang
// ẩn trông y như đã chết. Cách theo tầm nhìn không đụng gì tới hai thứ đó.
//
// KHÔNG THAY CHO HTTP/2. Bật HTTP/2 (cần HTTPS + tên miền) xoá hẳn giới hạn 6
// kết nối. Chừng nào chưa có tên miền thì đây là bản thay thế rẻ, và kể cả khi
// có HTTP/2 thì phần "tab ẩn không dựng lại trang" vẫn đáng giữ — nó cắt việc
// thừa, không chỉ né một giới hạn. Dựng /home tốn ~163ms CPU (đo qua cgroup:
// 60 lượt = 9.76s CPU của container dashboard) trên MỘT tiến trình Node, mà
// broker phát theo clinic_id tới MỌI tab đang nghe (change_broker.py).

/** Một cái hẹn giờ. Kiểu do bên gọi định đoạt để test tiêm đồng hồ giả vào. */
export type Hen = unknown;

/** Gỡ bỏ một thứ đã đăng ký: đóng dòng, thôi nghe, huỷ hẹn. */
export type Go = () => void;

export interface CongCuNhip {
  /** Việc làm khi tới nhịp. Thực tế là `router.refresh()`. */
  lamMoi: () => void;
  /** Tab này có đang bị ẩn/che không. */
  dangAn: () => boolean;
  hen: (fn: () => void, ms: number) => Hen;
  huy: (h: Hen) => void;
  /** Gộp nhịp bao lâu. Mặc định 250ms. */
  tre?: number;
}

export interface Nhip {
  /** Có thay đổi — xin một lượt làm mới, gộp với những lượt xin liền kề. */
  nhan: () => void;
  /** Vừa nối lại sau một quãng mù — làm mới NGAY, không chờ gộp nhịp. */
  batKip: () => void;
  /** Gỡ bỏ. */
  dung: () => void;
}

/** 250ms: đủ để gộp một chuỗi thay đổi của cùng một thao tác (mở lượt khám đụng
 *  vài bảng) thành một lần dựng trang, đủ ngắn để người dùng không thấy độ trễ. */
export const TRE_MAC_DINH = 250;

/**
 * Gộp nhịp làm mới, và KHÔNG làm mới tab đang ẩn.
 *
 * Debounce vốn đã có từ trước và chạy đúng — nó gộp được nhiều sự kiện trong
 * MỘT tab. Thứ nó không làm được, và về nguyên tắc không thể làm được, là gộp
 * giữa các tab: mười tab nhận cùng một tin thì vẫn là mười lượt dựng trang.
 * Cách duy nhất cắt được chúng là đừng dựng cho tab không ai nhìn.
 */
export function taoNhipLamMoi(cong: CongCuNhip): Nhip {
  const tre = cong.tre ?? TRE_MAC_DINH;
  let hen: Hen | null = null;

  function huyHen() {
    if (hen !== null) {
      cong.huy(hen);
      hen = null;
    }
  }

  return {
    nhan() {
      // Ẩn thì bỏ hẳn lượt này, không ghi sổ và không hẹn: dòng sự kiện của tab
      // ẩn đã đóng rồi (xem `moDongTheoHien`), nên lúc hiện lại `batKip` sẽ làm
      // mới một lượt bất kể có bỏ lỡ gì hay không. Giữ thêm một cuốn sổ nợ ở
      // đây là giữ một thứ luôn luôn đúng — tức vô dụng.
      if (cong.dangAn()) return;
      huyHen();
      hen = cong.hen(() => {
        hen = null;
        // Kiểm lại lúc nổ: 250ms vừa qua người ta có thể đã chuyển tab.
        if (cong.dangAn()) return;
        cong.lamMoi();
      }, tre);
    },

    batKip() {
      if (cong.dangAn()) return;
      // KHÔNG gộp nhịp ở đây. Người ta vừa nhìn vào màn hình; 250ms nữa mới
      // thấy số đúng là 250ms nhìn vào số sai.
      huyHen();
      cong.lamMoi();
    },

    dung: huyHen,
  };
}

export interface CongCuDong {
  /** Mở dòng SSE thật. Trả hàm đóng. */
  moDong: (nhanTin: (t: string | null) => void) => Go;
  /** Tab này có đang bị ẩn/che không. */
  dangAn: () => boolean;
  /** Đăng ký nghe đổi tầm nhìn. Trả hàm thôi nghe. */
  ngheDoiHien: (fn: () => void) => Go;
  /** Việc phải làm với mỗi tin. */
  xuLy: (t: string | null) => void;
  /** Gọi sau khi dòng được mở LẠI — quãng vừa rồi mù, phải bắt kịp. */
  khiMoLai: () => void;
}

/**
 * Giữ dòng sự kiện CHỈ trong lúc tab đang hiện.
 *
 * Một kết nối cho mỗi tab người ta ĐANG NHÌN, thay vì một kết nối cho mỗi tab
 * đang mở. Mười tab trong một cửa sổ là một kết nối, còn năm chỗ trống.
 *
 * KHÔNG ĐỆM MỘT QUÃNG ÂN HẠN trước khi đóng. Đệm để tránh nối lại khi người ta
 * lướt nhanh qua vài tab nghe hợp lý, nhưng nó đúng là kiểu tích luỹ đã gây ra
 * cả vấn đề này: lướt qua sáu tab trong quãng ân hạn là sáu dòng cùng mở, tức
 * trình duyệt đứng hình lần nữa. Nối lại thì rẻ (một lượt gọi vài chục ms) và
 * cái giá của nó có trần; tích luỹ kết nối thì không.
 *
 * BỎ SÓT LÀ CHẮC CHẮN, KHÔNG PHẢI RỦI RO. Lúc đóng thì tab không biết gì về
 * những thay đổi xảy ra sau đó — nên mở lại là phải làm mới một lượt, không cần
 * hỏi "có bỏ lỡ gì không". Đó là việc của `khiMoLai`.
 */
export function moDongTheoHien(cong: CongCuDong): Go {
  let dongDong: Go | null = null;
  let daTungMo = false;

  function mo() {
    if (dongDong) return;
    dongDong = cong.moDong(cong.xuLy);
    // Lần mở ĐẦU không phải "mở lại": trang vừa dựng xong, dữ liệu đang mới.
    if (daTungMo) cong.khiMoLai();
    daTungMo = true;
  }

  function dong() {
    if (!dongDong) return;
    dongDong();
    dongDong = null;
  }

  if (!cong.dangAn()) mo();

  const thoiNghe = cong.ngheDoiHien(() => {
    if (cong.dangAn()) dong();
    else mo();
  });

  return () => {
    thoiNghe();
    dong();
  };
}

/**
 * Sự kiện `window` mà `RealtimeRefresher` bắn ra cho MỖI tin nhận được, kèm tên
 * bảng trong `detail` (`null` = tin méo hoặc không rõ bảng nào).
 *
 * VÌ SAO CÓ. Màn Đặt lịch từng tự mở EventSource thứ hai để nghe `slot_hold`
 * cho riêng nó — lý do chính đáng: nó chỉ muốn hỏi lại một endpoint nhẹ, không
 * muốn dựng lại toàn bộ cây server component như `RealtimeRefresher` làm. Cái
 * giá không thấy được lúc viết là một tab ở màn ấy nuốt HAI trong sáu kết nối
 * của trình duyệt thay vì một, tức phòng khám chạm trần chỉ sau ba tab.
 *
 * Nay dòng SSE có đúng một chỗ mở, còn đây là cách các màn lẻ nghe ké mà không
 * phải mở thêm kết nối nào. Lý do ban đầu vẫn được giữ nguyên: người nghe tự
 * quyết làm gì với tin, không ai bị ép dựng lại trang.
 */
export const SU_KIEN_BANG = "clinicai:bang-doi";
