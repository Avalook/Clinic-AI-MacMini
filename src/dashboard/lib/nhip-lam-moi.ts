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
// HAI VIỆC FILE NÀY LÀM:
//
//   1. `moDongSuKien` — bầu MỘT tab chủ giữ dòng SSE, rồi phát lại cho các tab
//      khác qua BroadcastChannel. Mười tab dùng một kết nối thay vì mười.
//
//   2. `taoNhipLamMoi` — tab đang ẩn thì KHÔNG dựng lại trang, chỉ ghi "có bỏ
//      lỡ" rồi làm mới lúc người ta quay lại nhìn. Broker phát theo clinic_id
//      tới MỌI tab (change_broker.py), nên một cú bấm của một người sinh một
//      lượt dựng trang trên từng tab; mà dựng /home tốn ~163ms CPU (đo qua
//      cgroup: 60 lượt = 9.76s CPU của container dashboard) trên một tiến trình
//      Node duy nhất. Tab không ai nhìn thì lượt dựng ấy vứt đi.
//
// KHÔNG THAY CHO HTTP/2. Bật HTTP/2 (cần HTTPS + tên miền) xoá hẳn giới hạn 6
// kết nối. Chừng nào chưa có tên miền thì đây là bản thay thế rẻ, và kể cả khi
// có HTTP/2 thì mục 2 vẫn đáng giữ — nó cắt việc thừa, không chỉ né giới hạn.

/** Một cái hẹn giờ. Kiểu do bên gọi định đoạt để test tiêm đồng hồ giả vào. */
export type Hen = unknown;

export interface CongCuNhip {
  /** Việc làm khi tới nhịp. Thực tế là `router.refresh()`. */
  lamMoi: () => void;
  /** Tab này có đang bị ẩn/che không. Thực tế là `() => document.hidden`. */
  dangAn: () => boolean;
  hen: (fn: () => void, ms: number) => Hen;
  huy: (h: Hen) => void;
  /** Gộp nhịp bao lâu. Mặc định 250ms. */
  tre?: number;
}

export interface Nhip {
  /** Có thay đổi — xin một lượt làm mới. */
  nhan: () => void;
  /** Người dùng quay lại nhìn tab này. */
  hienLai: () => void;
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
  let boLo = false;

  function nhan() {
    // Ẩn thì ghi nợ, không hẹn. Hẹn rồi bỏ qua lúc nổ cũng ra kết quả ấy, nhưng
    // để dành một cái hẹn trong tab nền là để dành một thứ trình duyệt sẽ bóp
    // nhịp rồi bắn dồn lúc quay lại.
    if (cong.dangAn()) {
      boLo = true;
      return;
    }
    if (hen !== null) cong.huy(hen);
    hen = cong.hen(() => {
      hen = null;
      // Kiểm lại lúc nổ: 250ms vừa qua người ta có thể đã chuyển sang tab khác.
      if (cong.dangAn()) {
        boLo = true;
        return;
      }
      boLo = false;
      cong.lamMoi();
    }, tre);
  }

  function hienLai() {
    // Không nợ thì thôi — quay lại một tab vừa mới làm mới xong mà dựng lại
    // trang thì chính là thứ file này sinh ra để bỏ.
    if (!boLo) return;
    boLo = false;
    if (hen !== null) {
      cong.huy(hen);
      hen = null;
    }
    // KHÔNG debounce ở đây. Người ta vừa nhìn vào màn hình; 250ms nữa mới thấy
    // số đúng là 250ms nhìn vào số sai.
    cong.lamMoi();
  }

  function dung() {
    if (hen !== null) {
      cong.huy(hen);
      hen = null;
    }
  }

  return { nhan, hienLai, dung };
}

/** Đóng một dòng / một kênh / một lượt xếp hàng. */
export type Go = () => void;

export interface Kenh {
  gui: (t: string | null) => void;
  dong: Go;
}

export interface CongCuDong {
  /** Mở dòng SSE thật. Trả hàm đóng. */
  moDong: (nhanTin: (t: string | null) => void) => Go;
  /**
   * Xin làm tab chủ (thực tế là `navigator.locks`). Gọi `duoc()` khi giành
   * được khoá; trả hàm để thôi làm chủ hoặc thôi xếp hàng.
   *
   * `null` = trình duyệt không có Web Locks.
   */
  xinLamChu: ((duoc: () => void) => Go) | null;
  /** Kênh phát lại giữa các tab (BroadcastChannel). `null` = không có. */
  moKenh: ((nhan: (t: string | null) => void) => Kenh) | null;
  /** Việc phải làm với mỗi tin, ở CHÍNH tab này. */
  xuLy: (t: string | null) => void;
}

/**
 * Một dòng SSE cho cả trình duyệt, thay vì một dòng cho mỗi tab.
 *
 * Tab nào giành được khoá thì mở dòng và phát lại mọi tin qua BroadcastChannel;
 * các tab còn lại chỉ nghe. Tab chủ đóng lại thì khoá tự nhả và một tab đang
 * xếp hàng lên thay — không cần ai canh, đó là việc của Web Locks.
 *
 * THIẾU MỘT TRONG HAI THÌ QUAY VỀ CÁCH CŨ. Không có Web Locks hoặc không có
 * BroadcastChannel thì mỗi tab tự mở dòng của mình, y như trước. Chậm hơn,
 * nhưng chạy — còn hơn một tab ngồi chờ tin không bao giờ tới.
 *
 * BẪY ĐÃ BIẾT: tab chủ có thể là một tab đang ẩn, và trình duyệt được phép
 * đóng băng tab nền. Lưới an toàn là nhịp poll dự phòng của từng tab ĐANG HIỆN
 * (xem `taoNhipLamMoi`) — tab người ta đang nhìn vẫn tự bắt kịp trong một nhịp
 * poll, kể cả khi tab chủ đã ngủ.
 */
export function moDongSuKien(cong: CongCuDong): Go {
  const { xinLamChu, moKenh } = cong;

  if (!xinLamChu || !moKenh) {
    return cong.moDong(cong.xuLy);
  }

  const kenh = moKenh(cong.xuLy);
  let dongDong: Go | null = null;

  const thoiXepHang = xinLamChu(() => {
    dongDong = cong.moDong((t) => {
      // Tab chủ vừa xử lý cho mình, vừa phát lại cho các tab khác. Hai việc
      // tách rời nhau: tab chủ đang ẩn thì `xuLy` của nó sẽ bỏ lượt dựng trang,
      // nhưng tin vẫn phải đi tiếp — các tab kia có thể đang hiện.
      cong.xuLy(t);
      kenh.gui(t);
    });
  });

  return () => {
    if (dongDong) dongDong();
    thoiXepHang();
    kenh.dong();
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
 * Nay dòng SSE có đúng một chỗ mở (xem `moDongSuKien`), còn đây là cách các màn
 * lẻ nghe ké mà không phải mở thêm kết nối nào. Lý do ban đầu vẫn được giữ
 * nguyên: người nghe tự quyết làm gì với tin, không ai bị ép dựng lại trang.
 */
export const SU_KIEN_BANG = "clinicai:bang-doi";
