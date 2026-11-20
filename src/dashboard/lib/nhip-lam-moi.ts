// NHỊP LÀM MỚI VÀ DÒNG SỰ KIỆN — phần quyết định, tách khỏi React để test được.
//
// Hai luật, lý do và số đo đầy đủ ở docs/adr/0016-nhip-lam-moi.md:
// 1. Tab ẩn không giữ kết nối SSE và không dựng lại trang (21/08/2026: HTTP/1.1
//    chỉ 6 kết nối mỗi origin — tab thứ sáu làm cả trình duyệt đứng).
// 2. Tin dồn không biến thành một lượt dựng trang mỗi giây (20/11/2026: /me 429
//    → "Máy chủ đang bận"). Xem `khoangToiThieu`.

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
  /**
   * LỆCH NGẪU NHIÊN cộng thêm vào nhịp gộp, 0..jitter ms (mặc định 0 = không lệch).
   *
   * VÌ SAO (đo prod 14/10/2026). CPU dashboard + api + db vọt ĐỒNG LOẠT rồi tụt
   * về ~0 trong vài giây: một tin tới, mọi tab đang mở cùng nổ hẹn 250ms ở CÙNG
   * tích tắc và cùng hỏi lại. Lệch ngẫu nhiên rải đỉnh ấy ra — tổng số lượt hỏi
   * không đổi, nhưng không còn dồn vào một giây.
   */
  jitter?: number;
  /**
   * Trần chờ tính từ tin ĐẦU của một chuỗi tin liền nhau (mặc định: không trần).
   *
   * Debounce thuần cứ có tin mới là hẹn lại từ đầu — dòng tin đều đặn dưới 250ms
   * một tin thì lượt làm mới không bao giờ nổ, màn đứng hình. Có trần thì chờ tối
   * đa `choToiDa` (+ `jitter`) kể từ tin đầu rồi làm mới, tin còn chảy tiếp cũng vậy.
   */
  choToiDa?: number;
  /**
   * KHOẢNG TỐI THIỂU giữa hai lượt làm mới do TIN gây ra (mặc định: không có).
   * Phải đi kèm `choToiDa` (không có trần thì tin chảy đều sẽ dời hẹn mãi).
   *
   * VÌ SAO — xem docs/adr/0016-nhip-lam-moi.md mục 20/11/2026: tin dồn → mỗi tab
   * dựng lại trang ~1 lần/giây → `/me` 429 → "Máy chủ đang bận". Tin LẺ sau lúc
   * yên vẫn ~1 giây như cũ; tin dồn thì chờ đủ khoảng (bão dày ≥ `TIN_DAY` tin:
   * gấp đôi), luôn có một lượt SAU tin cuối. `batKip` không bị chặn.
   */
  khoangToiThieu?: number;
  /** Đồng hồ (ms). Mặc định `Date.now`; test tiêm đồng hồ giả. */
  bayGio?: () => number;
  /** Số ngẫu nhiên [0,1). Mặc định `Math.random`; test tiêm số cố định. */
  rand?: () => number;
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

/** Số tin trong MỘT lần chờ coi là bão dày (script ghi hàng loạt). Quầy đông
 *  khách: vài tin mỗi vài giây — không chạm. */
export const TIN_DAY = 10;

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
  const jitter = cong.jitter ?? 0;
  const bayGio = cong.bayGio ?? Date.now;
  const rand = cong.rand ?? Math.random;
  let hen: Hen | null = null;
  // Giờ của tin ĐẦU trong chuỗi đang chờ; chỉ có nghĩa khi `hen !== null`.
  let dauChuoi = 0;
  // Giờ lượt làm mới gần nhất (để giữ `khoangToiThieu`).
  let lanCuoi = Number.NEGATIVE_INFINITY;
  // Bão DÀY (≥ TIN_DAY tin trong một lần chờ — script ghi hàng loạt, không phải
  // người bấm) thì nhân đôi khoảng; yên đủ lâu thì về 1.
  let heSo = 1;
  let soTinCho = 0;
  const khoang = () => (cong.khoangToiThieu ?? 0) * heSo;

  function lamMoi() {
    lanCuoi = bayGio();
    cong.lamMoi();
  }

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
      const bay = bayGio();
      let cho = tre;
      if (hen === null) {
        dauChuoi = bay;
        soTinCho = 1;
        if (bay - lanCuoi >= 4 * (cong.khoangToiThieu ?? 0)) heSo = 1;
      } else if (cong.choToiDa !== undefined) {
        soTinCho += 1;
        const daCho = bay - dauChuoi;
        // Quá trần thì GIỮ NGUYÊN hẹn đang chạy — hẹn lại là dời nó thêm một
        // lượt lệch ngẫu nhiên, và dòng tin chảy mãi sẽ dời mãi.
        if (daCho >= cong.choToiDa) return;
        cho = Math.min(tre, cong.choToiDa - daCho);
      }
      huyHen();
      const lech = jitter > 0 ? Math.floor(rand() * (jitter + 1)) : 0;
      // Tin dồn: chưa đủ khoảng kể từ lượt trước thì dời tới đúng lúc đủ. Tin
      // tới tiếp trong lúc chờ rơi vào nhánh `choToiDa` ở trên (đã quá trần →
      // giữ nguyên hẹn), nên hẹn này không bị dời mãi. Kẹp ≤ một khoảng: đồng hồ
      // máy bị chỉnh lùi thì `lanCuoi` nằm ở tương lai (đo test: chờ 103 giây).
      const conThieu = Math.min(lanCuoi + khoang() - bay, khoang());
      hen = cong.hen(() => {
        hen = null;
        heSo = soTinCho >= TIN_DAY ? 2 : 1;
        // Kiểm lại lúc nổ: 250ms vừa qua người ta có thể đã chuyển tab.
        if (cong.dangAn()) return;
        lamMoi();
      }, Math.max(cho + lech, conThieu));
    },

    batKip() {
      if (cong.dangAn()) return;
      // KHÔNG gộp nhịp ở đây. Người ta vừa nhìn vào màn hình; 250ms nữa mới
      // thấy số đúng là 250ms nhìn vào số sai. Cũng không lệch ngẫu nhiên: đây
      // là một tab vừa được nhìn, không phải mười tab cùng nhận một tin.
      huyHen();
      lamMoi();
    },

    dung: huyHen,
  };
}

/**
 * Nhịp mặc định cho người NGHE TIN (`useNgheBang`, `RealtimeRefresher`): gộp
 * 250ms, trần 600ms kể từ tin đầu, lệch thêm 0–400ms. Xấu nhất ~1 giây từ lúc có
 * thay đổi thật tới lúc màn hỏi lại — đủ để người đứng quầy không thấy độ trễ.
 * Tin DỒN (script ghi hàng loạt, nhiều người cùng thao tác) thì hai lượt cách nhau
 * ít nhất 3 giây: ≤ ~20 lượt/phút × ~7 API ≈ 140, dưới ngưỡng cảnh báo 200 của
 * `runaway_guard` (trần 400/phút/tài khoản).
 */
export const NHIP_NGHE_TIN = { choToiDa: 600, jitter: 400, khoangToiThieu: 3_000 } as const;

export interface CongCuNoiLai {
  /** Đóng dòng hỏng và mở dòng mới. */
  moLai: () => void;
  hen: (fn: () => void, ms: number) => Hen;
  huy: (h: Hen) => void;
  /** Số ngẫu nhiên [0,1). Mặc định `Math.random`. */
  rand?: () => number;
  /** Chờ lần đầu (ms). Mặc định 2s. */
  coSoMs?: number;
  /** Trần chờ (ms). Mặc định 60s. */
  tranMs?: number;
}

export interface NoiLai {
  /** Dòng vừa hỏng hẳn — hẹn nối lại, mỗi lần hỏng liên tiếp chờ gấp đôi. */
  loi: () => void;
  /** Dòng vừa mở được — quên các lần hỏng trước. */
  thanhCong: () => void;
  /** Gỡ: huỷ hẹn (tab ẩn, rời màn). */
  dung: () => void;
}

/**
 * Nối lại dòng SSE hỏng HẲN, chờ gấp đôi mỗi lần, có trần, có lệch ngẫu nhiên.
 *
 * EventSource chỉ tự nối lại khi mất MẠNG (readyState quay về CONNECTING). Khi máy
 * chủ trả 4xx/5xx hoặc sai content-type — đúng lúc đang deploy, hay API quá tải
 * trả 502 — nó BỎ CUỘC (CLOSED) và không nối nữa: màn mất tin tức thời tới lần
 * đổi tab kế. Hàm này bịt lỗ ấy, mà không quay vòng nối-lại-mỗi-3-giây đúng lúc
 * máy chủ đang khổ: 2s → 4s → 8s … tối đa 60s, mỗi lần chỉ chờ nửa tới đủ thời
 * lượng (`rand`) để các máy không nối lại cùng tích tắc.
 */
export function taoNoiLai(cong: CongCuNoiLai): NoiLai {
  const coSo = cong.coSoMs ?? 2_000;
  const tran = cong.tranMs ?? 60_000;
  const rand = cong.rand ?? Math.random;
  let soLanHong = 0;
  let hen: Hen | null = null;

  function huyHen() {
    if (hen !== null) {
      cong.huy(hen);
      hen = null;
    }
  }

  return {
    loi() {
      // Đã hẹn rồi thì thôi: `error` có thể bắn liền mấy lần cho cùng một lần hỏng.
      if (hen !== null) return;
      const thoiLuong = Math.min(tran, coSo * 2 ** Math.min(soLanHong, 16));
      soLanHong += 1;
      const cho = Math.round(thoiLuong / 2 + rand() * (thoiLuong / 2));
      hen = cong.hen(() => {
        hen = null;
        cong.moLai();
      }, cho);
    },
    thanhCong() {
      soLanHong = 0;
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
    // Lần mở ĐẦU (lúc trang vừa dựng, tab đang hiện) không phải "mở lại": dữ
    // liệu đang mới.
    if (daTungMo) cong.khiMoLai();
    daTungMo = true;
  }

  function dong() {
    if (!dongDong) return;
    dongDong();
    dongDong = null;
  }

  // Mở trang trong tab NỀN (Ctrl+bấm link, 30/09/2026): trang dựng lúc tải,
  // nhưng từ lúc ấy tới lúc được nhìn thì không có dòng nào — quãng đó CŨNG mù.
  // Nên lần mở dòng đầu tiên, khi tới muộn, vẫn là một lần bắt kịp. Trước đây
  // `LiveBoardSync` tự nghe `visibilitychange` nên các màn điều phối không lộ lỗ
  // này; nay nó thôi nghe (một lần đổi tab từng thành ba lần dựng trang).
  if (!cong.dangAn()) mo();
  else daTungMo = true;

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

/**
 * Sự kiện `window`: lưu phiếu Sản khoa vừa ghi hai ô kinh cuối / dự kiến sinh
 * sang thai kỳ (máy chủ trả `thai_ky` — 29/09/2026). `detail` = mã khách. Khối
 * Thai kỳ bên dưới phiếu nghe để nạp lại; bảng `pregnancy` không phát tin
 * LISTEN/NOTIFY nên `SU_KIEN_BANG` không với tới.
 */
export const SU_KIEN_THAI_KY = "clinicai:thai-ky-doi";

/**
 * Tình trạng dòng SSE, cho các chỉ báo "cập nhật liên tục / mất kết nối".
 *
 * VÌ SAO CÓ (27/09/2026). Hai chỉ báo ở trang chủ và lịch hẹn từng đọc tình
 * trạng websocket của Supabase Realtime qua một kênh rỗng. Nhưng tin thật của
 * hệ thống không đi đường ấy từ 06/08 — nó đi LISTEN/NOTIFY → SSE. Chấm xanh
 * khi ấy nói về một kết nối không chở tin nào của mình: kênh này có thể sống
 * trong lúc dòng SSE đã chết, và ngược lại. Nay chỉ báo đọc đúng dòng đang
 * chở tin.
 *
 * - `dang-noi`: chưa mở, hoặc đang mở lại (tab vừa hiện).
 * - `song`: dòng đang mở, tin tới được.
 * - `rot`: dòng lỗi và chưa nối lại được sau một quãng ân hạn.
 */
export type TrangThaiDong = "dang-noi" | "song" | "rot";

export interface KhoTrangThai<T> {
  doc: () => T;
  dat: (moi: T) => void;
  /** Đăng ký nghe đổi. Trả hàm thôi nghe — đúng hình `useSyncExternalStore`. */
  nghe: (fn: () => void) => Go;
}

/** Một ô giá trị có người nghe. Tách thành hàm để test không đụng bản dùng chung. */
export function taoKhoTrangThai<T>(dau: T): KhoTrangThai<T> {
  let hienTai = dau;
  const nguoiNghe = new Set<() => void>();
  return {
    doc: () => hienTai,
    dat(moi) {
      // Không đổi thì không báo — mỗi lời báo là một lượt render ở người nghe.
      if (Object.is(moi, hienTai)) return;
      hienTai = moi;
      for (const fn of [...nguoiNghe]) fn();
    },
    nghe(fn) {
      nguoiNghe.add(fn);
      return () => {
        nguoiNghe.delete(fn);
      };
    },
  };
}

/** Bản dùng chung cho cả tab. `RealtimeRefresher` là người GHI duy nhất. */
export const trangThaiDong = taoKhoTrangThai<TrangThaiDong>("dang-noi");

/** Khi dòng SSE đang `song`, nhịp hỏi dự phòng của chuông chỉ hỏi thật nếu đã
 *  chừng này ms không có lượt hỏi nào (tin tức thời đã lo phần còn lại). */
export const POLL_DU_PHONG_KHI_SONG_MS = 90_000;

/**
 * Nhịp hỏi dự phòng (20s) tới hạn — có hỏi thật không?
 *
 * VÌ SAO (đo prod 14/10/2026). Chuông thông báo và "ca của tôi" hỏi mỗi 20 giây
 * ở MỌI tab đang hiện, kể cả khi dòng SSE đang chở tin đúng bảng ấy: 1.239 +
 * 1.112 lượt trong 30 phút (~9% tải) cho dữ liệu hầu như không đổi. Dòng `song`
 * thì tin mới tới ngay, nhịp chỉ còn là lưới an toàn nên thưa đi. Dòng không
 * `song` (đang nối, đã rớt) thì giữ nhịp 20s như cũ — lúc ấy nhịp mới là nguồn tin.
 *
 * `daQuaMs`: từ lượt hỏi gần nhất (do bất kỳ nguồn nào) tới giờ.
 */
export function canHoiDuPhong(
  dong: TrangThaiDong,
  daQuaMs: number,
  thuaMs: number = POLL_DU_PHONG_KHI_SONG_MS,
): boolean {
  return dong !== "song" || daQuaMs >= thuaMs;
}

/** Lỗi dòng bao lâu mới báo "mất kết nối". EventSource tự nối lại sau ~3 giây;
 *  báo ngay mỗi lần chớp là dạy người ta lờ đi lời báo thật. */
export const AN_HAN_ROT_MS = 5_000;
