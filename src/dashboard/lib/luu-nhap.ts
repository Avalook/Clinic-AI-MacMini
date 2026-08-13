// Giữ lại thứ đang gõ dở khi trang bị tải lại, tab chết, hoặc máy trạm mất điện.
//
// VÌ SAO CẦN. Yêu cầu của phòng khám (bảng "tình huống phát sinh", mục 4): *"Mất
// mạng hoặc tải lại trang khi đang nhập → hệ thống không tạo dữ liệu dở dang;
// người dùng biết dữ liệu đã được lưu hay chưa"*. Trước file này, màn bệnh án
// không giữ gì cả: bác sĩ gõ xong một tờ dài, lỡ F5 hay mất điện là gõ lại từ
// đầu, và không có dấu hiệu nào cho biết đã mất.
//
// VÌ SAO `localStorage` CHỨ KHÔNG PHẢI `sessionStorage`. sessionStorage chết
// cùng tab — đúng những tình huống cần cứu nhất (mất điện, trình duyệt sập,
// đóng nhầm tab) thì nó không còn gì. Cái giá phải trả là dữ liệu bệnh nhân nằm
// trên đĩa máy trạm, nên bốn chốt dưới đây không phải trang trí:
//
//   1. KHOÁ GẮN VỚI NGƯỜI ĐANG ĐĂNG NHẬP. Quầy lễ tân dùng chung một máy; nháp
//      của người trước không được hiện ra cho người sau.
//   2. HẠN 24 GIỜ. Nháp quá hạn bị bỏ khi đọc và bị dọn khi ghi — không tích tụ
//      bệnh án của cả tháng trên máy.
//   3. XOÁ NGAY KHI LƯU THÀNH CÔNG. Nháp chỉ tồn tại trong lúc còn rủi ro mất.
//   4. CHỈ LƯU THỨ NGƯỜI DÙNG GÕ, không lưu hồ sơ tải từ máy chủ về.
//
// NHÁP KHÔNG PHẢI BẢN LƯU. Nó không đi đâu cả, không ai khác đọc được, và không
// thay thế việc bấm Lưu. Màn hình phải nói đúng điều đó khi mời khôi phục —
// người dùng cần biết "cái này chưa được lưu", chứ không phải tưởng đã xong.

/** Kho tối thiểu — để test được mà không cần trình duyệt. */
export interface KhoNhap {
  getItem(k: string): string | null;
  setItem(k: string, v: string): void;
  removeItem(k: string): void;
  key(i: number): string | null;
  readonly length: number;
}

const TIEN_TO = "clinicai:nhap:";
export const HAN_MS = 24 * 60 * 60 * 1000;

/** Khoá của một bản nháp. `staffId` rỗng = không ai đăng nhập → không lưu. */
export function khoaNhap(
  staffId: string | null | undefined,
  man: string,
  id: string | null | undefined,
): string | null {
  if (!staffId || !id) return null;
  return `${TIEN_TO}${staffId}:${man}:${id}`;
}

interface BanNhap<T> {
  luc: number;
  giaTri: T;
}

/** Dọn mọi bản nháp quá hạn. Trả về số bản đã bỏ. */
export function donNhapCu(kho: KhoNhap, now: number): number {
  const bo: string[] = [];
  for (let i = 0; i < kho.length; i++) {
    const k = kho.key(i);
    if (!k || !k.startsWith(TIEN_TO)) continue;
    try {
      const b = JSON.parse(kho.getItem(k) || "") as BanNhap<unknown>;
      if (!b || typeof b.luc !== "number" || now - b.luc > HAN_MS) bo.push(k);
    } catch {
      bo.push(k); // hỏng thì bỏ — một bản nháp không đọc được thì vô dụng
    }
  }
  bo.forEach((k) => kho.removeItem(k));
  return bo.length;
}

export function ghiNhap<T>(kho: KhoNhap, khoa: string, giaTri: T, now: number): void {
  try {
    kho.setItem(khoa, JSON.stringify({ luc: now, giaTri } satisfies BanNhap<T>));
  } catch {
    // Hết chỗ hoặc trình duyệt chặn (chế độ riêng tư). Không lưu được thì thôi:
    // form vẫn dùng bình thường, chỉ là mất lưới an toàn. Không được ném ở đây —
    // ném trong lúc gõ sẽ làm hỏng chính cái nó định cứu.
  }
}

/** Đọc nháp còn hạn. `null` = không có, hết hạn, hoặc hỏng. */
export function docNhap<T>(kho: KhoNhap, khoa: string, now: number): BanNhap<T> | null {
  try {
    const b = JSON.parse(kho.getItem(khoa) || "") as BanNhap<T>;
    if (!b || typeof b.luc !== "number") return null;
    if (now - b.luc > HAN_MS) {
      kho.removeItem(khoa);
      return null;
    }
    return b;
  } catch {
    return null;
  }
}

export function xoaNhap(kho: KhoNhap, khoa: string): void {
  try {
    kho.removeItem(khoa);
  } catch {
    /* xoá không được thì hạn 24h vẫn dọn hộ */
  }
}

/** "2 phút trước" — để câu mời khôi phục nói rõ nháp cũ tới mức nào. */
export function moTaLuc(luc: number, now: number): string {
  const giay = Math.max(0, Math.round((now - luc) / 1000));
  if (giay < 60) return "vừa xong";
  const phut = Math.round(giay / 60);
  if (phut < 60) return `${phut} phút trước`;
  const gio = Math.round(phut / 60);
  return `${gio} giờ trước`;
}
