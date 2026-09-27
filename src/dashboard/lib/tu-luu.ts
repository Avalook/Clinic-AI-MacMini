// TỰ LƯU CHẮC CHẮN — hàng đợi lưu dùng chung cho phiếu khám, đơn thuốc, phiếu
// kết quả, ô tư vấn (góp ý phòng khám B9, đợt 3 — 27/09/2026).
//
// Tuyền đã chốt KHÔNG có nút "Lưu hồ sơ". Bù lại, tự lưu phải CHẮC:
//
//   · TUẦN TỰ. Không bao giờ có hai lần lưu cùng bay. Gõ tiếp trong lúc một lần
//     đang bay thì lần sau đợi, và gửi bản MỚI NHẤT (gộp mọi phím gõ giữa chừng).
//     Hai lần bay song song là nguồn của lỗi "người khác vừa lưu" oan ở phiếu
//     kết quả: lần sau mang số revision cũ vì lần trước chưa về.
//   · KHÔNG MẤT CHỮ KHI RỜI MÀN. Hẹn lưu không bị xoá im lặng — rời màn thì lưu
//     nốt (`luuNgay`), đóng tab thì gửi bằng `keepalive` (`guiKhiRoiTrang`).
//   · LỖI MẠNG TỰ THỬ LẠI, giãn cách 2 · 4 · 8 · 16 · 30 giây. Lỗi NGHIỆP VỤ
//     (4xx: sai dữ liệu, người khác vừa sửa, thiếu lý do…) KHÔNG thử lại — thử
//     lại y nguyên thì máy chủ lại từ chối y nguyên; màn nói ra để người sửa.
//   · LUÔN BIẾT TRẠNG THÁI: {dang_luu, chua_luu, loi, luu_luc}.
//
// Hàng đợi KHÔNG giữ dữ liệu. Nó chỉ đếm "có thay đổi chưa tới máy chủ"; hàm
// `gui` của màn tự đọc bản mới nhất lúc gửi (ref). Nhờ vậy lần gửi sau luôn
// thấy kết quả của lần trước (revision mới, mã dòng thuốc vừa tạo).
//
// Tệp này là JS thuần, không React — test bằng đồng hồ giả (`tu-luu.test.mts`).
// Móc React ở `use-tu-luu.ts`.

export type KetQuaGui = { ok: true } | { ok: false; loi: string; thuLai: boolean };

export interface TrangThaiLuu {
  /** Đang có một lần lưu bay tới máy chủ. */
  dang_luu: boolean;
  /** Có thay đổi CHƯA tới máy chủ (kể cả đang bay). */
  chua_luu: boolean;
  /** Lỗi của lần lưu gần nhất; null = lần gần nhất thành công. */
  loi: string | null;
  /** Hàng đợi sẽ tự thử lại (lỗi mạng). false = phải bấm [Thử lại] hoặc gõ tiếp. */
  tu_thu_lai: boolean;
  /** Lúc lưu thành công gần nhất. */
  luu_luc: Date | null;
}

export const TRANG_THAI_DAU: TrangThaiLuu = {
  dang_luu: false,
  chua_luu: false,
  loi: null,
  tu_thu_lai: false,
  luu_luc: null,
};

export const LOI_MAT_KET_NOI = "Mất kết nối — nội dung CHƯA được lưu.";

/**
 * Mã HTTP nào đáng thử lại. 0 = không tới được máy chủ (mạng rớt, trình duyệt
 * huỷ). 408/425/429 và 5xx là máy chủ bận/đứt tạm. Mọi 4xx khác là máy chủ ĐÃ
 * ĐỌC và từ chối — gửi lại y nguyên vô ích. Rác → coi như mạng (thử lại).
 */
export function nenThuLai(status: unknown): boolean {
  if (typeof status !== "number" || !Number.isFinite(status)) return true;
  if (status === 0) return true;
  if (status === 408 || status === 425 || status === 429) return true;
  return status >= 500;
}

const THU_LAI_MS = [2000, 4000, 8000, 16000, 30000];

/** Khoảng chờ trước lần thử lại thứ `lan` (1, 2, …). Rác → lần đầu. */
export function choThuLaiMs(lan: unknown): number {
  const n = typeof lan === "number" && Number.isFinite(lan) ? Math.floor(lan) : 1;
  const i = Math.min(Math.max(n, 1), THU_LAI_MS.length) - 1;
  return THU_LAI_MS[i];
}

/** Gộp trạng thái hai hàng đợi của CÙNG một màn (phiếu + đơn thuốc). */
export function gopTrangThai(a: TrangThaiLuu, b: TrangThaiLuu): TrangThaiLuu {
  const luc =
    a.luu_luc && b.luu_luc
      ? a.luu_luc > b.luu_luc
        ? a.luu_luc
        : b.luu_luc
      : (a.luu_luc ?? b.luu_luc);
  return {
    dang_luu: a.dang_luu || b.dang_luu,
    chua_luu: a.chua_luu || b.chua_luu,
    loi: a.loi ?? b.loi,
    tu_thu_lai: a.loi ? a.tu_thu_lai : b.tu_thu_lai,
    luu_luc: luc,
  };
}

/** Đồng hồ tiêm vào được — test dùng đồng hồ giả. */
export interface DongHo {
  hen: (fn: () => void, ms: number) => unknown;
  huy: (h: unknown) => void;
  bayGio: () => Date;
}

const DONG_HO_THAT: DongHo = {
  hen: (fn, ms) => setTimeout(fn, ms),
  huy: (h) => clearTimeout(h as ReturnType<typeof setTimeout>),
  bayGio: () => new Date(),
};

export interface TuyChonHangDoi {
  /** Gửi BẢN MỚI NHẤT lên máy chủ. `keepalive` = trang đang đóng. */
  gui: (keepalive: boolean) => Promise<KetQuaGui>;
  /** Khoảng lặng sau phím gõ cuối trước khi lưu. */
  choMs: number;
  onDoi?: (tt: TrangThaiLuu) => void;
  dongHo?: DongHo;
}

/** Số vòng tối đa `luuNgay` chờ — người vẫn gõ liên tục thì không kẹt mãi. */
const VONG_TOI_DA = 8;

export class HangDoiLuu {
  private readonly tuyChon: TuyChonHangDoi;
  private readonly dongHo: DongHo;
  private gui: (keepalive: boolean) => Promise<KetQuaGui>;
  /** Tăng mỗi lần có thay đổi. */
  private phienBan = 0;
  /** Phiên bản đã tới máy chủ. chua_luu ⇔ phienBan > daLuuDen. */
  private daLuuDen = 0;
  private dangBay: Promise<boolean> | null = null;
  /** Phiên bản mà lần đang bay mang theo. */
  private banDangBay = 0;
  private henCho: unknown = null;
  private henThuLai: unknown = null;
  private lanLoi = 0;
  private loi: string | null = null;
  private luuLuc: Date | null = null;

  constructor(tuyChon: TuyChonHangDoi) {
    this.tuyChon = tuyChon;
    this.dongHo = tuyChon.dongHo ?? DONG_HO_THAT;
    this.gui = tuyChon.gui;
  }

  /** Thay hàm gửi (màn render lại với closure mới). Lần gửi sau dùng hàm này. */
  datGui(gui: (keepalive: boolean) => Promise<KetQuaGui>): void {
    this.gui = gui;
  }

  get trangThai(): TrangThaiLuu {
    return {
      dang_luu: this.dangBay !== null,
      chua_luu: this.phienBan > this.daLuuDen,
      loi: this.loi,
      tu_thu_lai: this.henThuLai !== null,
      luu_luc: this.luuLuc,
    };
  }

  private phat(): void {
    this.tuyChon.onDoi?.(this.trangThai);
  }

  private huyHen(): void {
    if (this.henCho !== null) this.dongHo.huy(this.henCho);
    if (this.henThuLai !== null) this.dongHo.huy(this.henThuLai);
    this.henCho = null;
    this.henThuLai = null;
  }

  /** Có thay đổi mới → hẹn lưu sau `choMs` (gõ tiếp thì dời hẹn). */
  danhDau(): void {
    this.phienBan += 1;
    if (this.henCho !== null) this.dongHo.huy(this.henCho);
    this.henCho = this.dongHo.hen(() => {
      this.henCho = null;
      void this.bom();
    }, this.tuyChon.choMs);
    this.phat();
  }

  /**
   * Dữ liệu vừa nạp lại từ máy chủ (tải lại sau xung đột, đổi phiếu) — những
   * gì chưa lưu đã bị bản máy chủ thay. Không gửi gì, xoá hẹn và lỗi.
   */
  lamSach(): void {
    this.huyHen();
    this.daLuuDen = this.phienBan;
    this.loi = null;
    this.lanLoi = 0;
    this.phat();
  }

  /** Gửi một lần nếu còn thay đổi. Đang có lần bay thì trả chính lần ấy. */
  private bom(): Promise<boolean> {
    if (this.dangBay) return this.dangBay;
    if (this.phienBan <= this.daLuuDen) return Promise.resolve(this.loi === null);
    if (this.henThuLai !== null) {
      this.dongHo.huy(this.henThuLai);
      this.henThuLai = null;
    }
    const ban = this.phienBan;
    this.banDangBay = ban;
    const bay = (async (): Promise<boolean> => {
      let kq: KetQuaGui;
      try {
        kq = await this.gui(false);
      } catch {
        kq = { ok: false, loi: LOI_MAT_KET_NOI, thuLai: true };
      }
      if (kq.ok) {
        this.daLuuDen = Math.max(this.daLuuDen, ban);
        this.loi = null;
        this.lanLoi = 0;
        this.luuLuc = this.dongHo.bayGio();
        return true;
      }
      this.loi = kq.loi || LOI_MAT_KET_NOI;
      if (kq.thuLai) {
        this.lanLoi += 1;
        this.henThuLai = this.dongHo.hen(() => {
          this.henThuLai = null;
          void this.bom();
        }, choThuLaiMs(this.lanLoi));
      } else {
        this.lanLoi = 0;
      }
      return false;
    })();
    this.dangBay = bay;
    this.phat();
    void bay.then((ok) => {
      this.dangBay = null;
      this.phat();
      // Gõ thêm trong lúc bay và hẹn đã tới giờ → gửi ngay bản mới nhất.
      if (ok && this.phienBan > this.daLuuDen && this.henCho === null) void this.bom();
    });
    return bay;
  }

  /**
   * Lưu NGAY mọi thứ còn chưa lưu và đợi tới khi xong. true = máy chủ đã có
   * hết. Dùng cho [Lưu ngay], [Thử lại], trước Hoàn tất, và lúc rời màn.
   */
  async luuNgay(): Promise<boolean> {
    if (this.henCho !== null) {
      this.dongHo.huy(this.henCho);
      this.henCho = null;
    }
    for (let vong = 0; vong < VONG_TOI_DA; vong += 1) {
      if (this.dangBay) {
        const ok = await this.dangBay;
        // Chờ `.then` dọn `dangBay` chạy xong trước khi hỏi tiếp.
        await Promise.resolve();
        if (!ok) return false;
        continue;
      }
      if (this.phienBan <= this.daLuuDen) return this.loi === null;
      const ok = await this.bom();
      await Promise.resolve();
      if (!ok) return false;
    }
    return this.phienBan <= this.daLuuDen && this.loi === null;
  }

  /**
   * Trang đang đóng / tải lại: gửi bằng `keepalive` để trình duyệt giữ yêu cầu
   * sau khi trang chết. Không đợi kết quả — không còn ai để báo.
   */
  guiKhiRoiTrang(): void {
    if (this.phienBan <= this.daLuuDen) return;
    // Lần đang bay đã mang đủ mọi thay đổi → không gửi trùng (đơn thuốc: hai
    // lần gửi cùng dòng chưa có mã là hai dòng trùng).
    if (this.dangBay && this.banDangBay >= this.phienBan) return;
    this.huyHen();
    void this.gui(true).catch(() => undefined);
  }

  /** Huỷ mọi hẹn, KHÔNG gửi (dữ liệu không còn thuộc về màn này). */
  dung(): void {
    this.huyHen();
  }
}
