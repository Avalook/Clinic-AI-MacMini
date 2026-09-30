// NHỊP HỎI CHỈ CHẠY KHI TAB HIỆN — và QUAY LẠI TAB LÀ MỘT LẦN CẬP NHẬT.
//
// VÌ SAO FILE NÀY RA ĐỜI (đo prod 30/09/2026). Nhân viên mở nhiều tab cùng tài
// khoản và đổi tab liên tục: dòng SSE sống trung vị 9 giây, vì mỗi lần ẩn/hiện
// là đóng/mở lại (chủ ý — xem `lib/nhip-lam-moi`). Hai thứ đi kèm thì không chủ ý:
//
// 1. Các nhịp hỏi dự phòng (chuông 20s, ca của tôi 20s, hàng chờ phòng 60s,
//    hành trình 60s, điều phối 30s…) là `setInterval` trần — tab ẩn VẪN hỏi. Một
//    người mở năm tab là năm nhịp chạy song song cho bốn màn không ai nhìn.
// 2. Mỗi lần quay lại tab là một đợt dồn: `RealtimeRefresher` làm mới trang,
//    `LiveBoardSync` làm mới thêm một lần cho `visibilitychange` và một lần nữa
//    cho `focus`, chuông tự hỏi cho `visibilitychange` rồi hỏi lại cho tin
//    `null`. Tới ba lần `router.refresh()` và ~4 lời gọi /api cho MỘT lần đổi tab.
//
// Hai tiện ích dưới đây là luật chung cho cả hai chỗ, tách khỏi React để test.

/** Một cái hẹn giờ. Kiểu do bên gọi định đoạt để test tiêm đồng hồ giả vào. */
export type HenLap = unknown;

/** Gỡ bỏ: thôi nghe, huỷ hẹn. */
export type GoBo = () => void;

export interface CongNhipKhiHien {
  /** Tab này có đang bị ẩn/che không. */
  dangAn: () => boolean;
  /** Đăng ký nghe đổi tầm nhìn. Trả hàm thôi nghe. */
  ngheDoiHien: (fn: () => void) => GoBo;
  henLap: (fn: () => void, ms: number) => HenLap;
  huyLap: (h: HenLap) => void;
}

export interface TuyChonNhipKhiHien {
  /**
   * Tab hiện lại thì chạy `viec` MỘT lần ngay (mặc định: có).
   *
   * Đặt `false` khi màn ĐÃ nghe `useNgheBang` / `SU_KIEN_BANG` / `SU_KIEN_DOI_CA`:
   * lúc tab hiện lại, `RealtimeRefresher` phát tin `null` (và rung chuông ca), nên
   * màn ấy đã tự hỏi lại một lần rồi. Hỏi thêm ở đây là lần thứ hai — đúng cái
   * dồn đang chữa.
   */
  hoiKhiHien?: boolean;
  /** Tiêm cổng giả cho test. Mặc định: `document` + `setInterval` thật. */
  cong?: CongNhipKhiHien;
}

function congTrinhDuyet(): CongNhipKhiHien {
  return {
    dangAn: () => document.visibilityState === "hidden",
    ngheDoiHien: (fn) => {
      document.addEventListener("visibilitychange", fn);
      return () => document.removeEventListener("visibilitychange", fn);
    },
    henLap: (fn, ms) => setInterval(fn, ms),
    huyLap: (h) => clearInterval(h as ReturnType<typeof setInterval>),
  };
}

/**
 * Thay cho `setInterval(viec, ms)` ở mọi nhịp hỏi máy chủ.
 *
 * - Tab ẩn: HUỶ hẳn nhịp (không chỉ bỏ lượt — không còn hẹn nào chạy nền).
 * - Tab hiện lại: đặt lại nhịp, và nếu `hoiKhiHien` thì chạy `viec` một lần ngay.
 * - KHÔNG chạy `viec` lúc bắt đầu: màn nào cũng đã tự nạp lượt đầu, giữ nguyên.
 *
 * Trả hàm gỡ — dùng thẳng làm giá trị trả về của `useEffect`, đúng chỗ
 * `() => clearInterval(t)` cũ.
 */
export function nhipKhiHien(
  viec: () => void,
  ms: number,
  tuyChon: TuyChonNhipKhiHien = {},
): GoBo {
  const cong = tuyChon.cong ?? congTrinhDuyet();
  const hoiKhiHien = tuyChon.hoiKhiHien ?? true;
  let hen: HenLap | null = null;

  function bat() {
    if (hen !== null) return;
    hen = cong.henLap(() => {
      // Phòng khi lỡ mất một tin đổi tầm nhìn: nổ lúc ẩn thì bỏ lượt.
      if (cong.dangAn()) return;
      viec();
    }, ms);
  }

  function tat() {
    if (hen === null) return;
    cong.huyLap(hen);
    hen = null;
  }

  if (!cong.dangAn()) bat();

  const thoiNghe = cong.ngheDoiHien(() => {
    if (cong.dangAn()) {
      tat();
      return;
    }
    // Hiện lại. Phòng thủ: nhịp đang chạy nghĩa là chưa từng ẩn (tin "hiện"
    // lặp lại), nên không hỏi thêm.
    if (hen !== null) return;
    bat();
    if (hoiKhiHien) viec();
  });

  return () => {
    thoiNghe();
    tat();
  };
}

export interface CongGopBatKip {
  /** Việc bắt kịp: làm mới trang + báo các màn tự hỏi lại. */
  viec: () => void;
  dangAn: () => boolean;
  bayGio: () => number;
  hen: (fn: () => void, ms: number) => HenLap;
  huy: (h: HenLap) => void;
  /** Hai lần bắt kịp cách nhau ít nhất bao lâu. Mặc định `CUA_SO_BAT_KIP_MS`. */
  cuaSo?: number;
}

export interface GopBatKip {
  /** Xin một lần bắt kịp (tab vừa hiện lại). */
  xin: () => void;
  dung: () => void;
}

/** 2 giây: lướt qua lại hai tab trong khoảng này là một thao tác, không phải hai. */
export const CUA_SO_BAT_KIP_MS = 2_000;

/**
 * Gộp các lần "bắt kịp sau quãng mù": tối đa MỘT lần mỗi `cuaSo`.
 *
 * Người lướt qua lại A → B → A trong một giây sẽ làm tab A hiện lại hai lần;
 * mỗi lần là một lượt dựng lại cả cây server component (~163ms CPU trên một
 * tiến trình Node) cộng một lượt hỏi của mọi màn tự fetch.
 *
 * KHÔNG BỎ, CHỈ HOÃN. Lần xin rơi vào cửa sổ được dời tới cuối cửa sổ, không bị
 * vứt: dòng SSE đã đóng suốt quãng ẩn (dù chỉ nửa giây), nên thay đổi trong
 * quãng ấy chỉ có lần bắt kịp này mới nhặt được. Vứt nó là để màn nói dối tới
 * nhịp dự phòng kế tiếp (60 giây).
 *
 * Tới giờ hoãn mà tab đã ẩn lại thì thôi: lần hiện sau sẽ xin lại.
 */
export function taoGopBatKip(cong: CongGopBatKip): GopBatKip {
  const cuaSo = cong.cuaSo ?? CUA_SO_BAT_KIP_MS;
  let lanCuoi = Number.NEGATIVE_INFINITY;
  let hoan: HenLap | null = null;

  function chay() {
    lanCuoi = cong.bayGio();
    cong.viec();
  }

  return {
    xin() {
      if (cong.dangAn()) return;
      if (hoan !== null) return; // đã có một lần chờ ở cuối cửa sổ — gộp vào đó
      const conLai = lanCuoi + cuaSo - cong.bayGio();
      if (conLai <= 0) {
        chay();
        return;
      }
      hoan = cong.hen(() => {
        hoan = null;
        if (cong.dangAn()) return;
        chay();
      }, conLai);
    },
    dung() {
      if (hoan !== null) {
        cong.huy(hoan);
        hoan = null;
      }
    },
  };
}
