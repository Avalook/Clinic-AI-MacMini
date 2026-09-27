// NGĂN GẬP — phần thuần của `components/ui/NganGap` (đợt 3, 27/09/2026).
//
// Nhớ đóng/mở THEO NGƯỜI DÙNG (trình duyệt của họ) bằng localStorage. Đây chỉ
// là tiện nghi hiển thị: đọc/ghi hỏng (duyệt ẩn danh, bị chặn, đầy) thì trả về
// mặc định, KHÔNG BAO GIỜ ném — một ngăn gập không được làm sập phiếu khám.

const TIEN_TO = "clinicai:ngan-gap:";

/** Kho tối thiểu — `window.localStorage` hoặc kho giả trong test. */
export interface KhoNho {
  getItem(k: string): string | null;
  setItem(k: string, v: string): void;
}

function khoMacDinh(): KhoNho | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** Trạng thái mở lúc đầu: đã nhớ "1"/"0" thì theo nhớ, còn lại theo mặc định. */
export function moBanDau(daNho: string | null | undefined, macDinh: boolean): boolean {
  if (daNho === "1") return true;
  if (daNho === "0") return false;
  return macDinh;
}

export function docNhoGap(khoa: string, kho: KhoNho | null = khoMacDinh()): string | null {
  if (!kho || !khoa) return null;
  try {
    return kho.getItem(TIEN_TO + khoa);
  } catch {
    return null;
  }
}

export function ghiNhoGap(khoa: string, mo: boolean, kho: KhoNho | null = khoMacDinh()): void {
  if (!kho || !khoa) return;
  try {
    kho.setItem(TIEN_TO + khoa, mo ? "1" : "0");
  } catch {
    // Kho đầy / bị chặn — bỏ qua, lần sau lại theo mặc định.
  }
}
