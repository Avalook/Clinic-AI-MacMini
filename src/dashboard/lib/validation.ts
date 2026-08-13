// Quy tắc nhập liệu CỨNG dùng chung (client form + server API), 1 nguồn sự thật.
//   - SĐT: số VN 10 chữ số, BẮT ĐẦU BẰNG 0, đầu số hợp lệ (cố định 02; di động
//     03/05/07/08/09). Không có số mở đầu bằng 1/2/4/6 hay thiếu số 0.
//   - CCCD: 12 chữ số; 3 số đầu là mã tỉnh (001–096).
// Trường rỗng = hợp lệ (các trường này tuỳ chọn); chỉ chặn khi CÓ nhập mà sai.

// 0 + (2 cố định | 3,5,7,8,9 di động) + 8 chữ số.
export const PHONE_RE = /^0[235789]\d{8}$/;
export const CCCD_RE = /^\d{12}$/;

/** Bỏ mọi ký tự không phải chữ số (dùng cho onChange ép "số viết liền"). */
export const digitsOnly = (s: string): string => (s ?? "").replace(/\D/g, "");

/**
 * Chuẩn hoá SĐT lúc gõ/dán (như form các trang lớn): bỏ ký tự lạ, đổi tiền tố
 * quốc tế +84 / 0084 / 84 → 0, cắt còn tối đa 10 số. KHÔNG báo lỗi — chỉ nắn
 * dữ liệu; tính hợp lệ để `phoneError` lo.
 */
export function normalizePhoneVi(raw: string): string {
  let d = (raw ?? "").replace(/\D/g, "");
  if (d.startsWith("0084")) d = "0" + d.slice(4);
  else if (d.startsWith("84") && d.length >= 11) d = "0" + d.slice(2);
  return d.slice(0, 10);
}

/**
 * Viết hoa chữ đầu MỖI từ cho tên riêng VN: "nguyễn thị hoa" → "Nguyễn Thị Hoa".
 * Gộp khoảng trắng thừa + cắt 2 đầu. Dùng \p{L} (cờ u) để bắt đúng chữ có dấu.
 * Áp lúc rời ô (onBlur) — KHÔNG ép lúc đang gõ để không phá bộ gõ Telex/VNI.
 */
export function toTitleCaseVi(s: string): string {
  return (s ?? "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim()
    .replace(/(^|\s)(\p{L})/gu, (_m, sep: string, ch: string) => sep + ch.toUpperCase());
}

/**
 * Bỏ dấu tiếng Việt + viết thường — tìm kiếm KHÔNG phân biệt dấu
 * ("Hoà" = "Hoa" = "hoa"). Khớp đúng cột patient.full_name_unaccent (migration
 * 039: lower + f_unaccent + đ→d), dùng chung cho lọc client lẫn query Supabase.
 */
export const unaccentVi = (s: string): string =>
  (s ?? "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();

/** null = hợp lệ (hoặc rỗng); chuỗi = thông báo lỗi. */
export function phoneError(v: string | null | undefined): string | null {
  const t = (v ?? "").trim();
  if (!t) return null;
  if (t.length !== 10) return "Số điện thoại phải gồm đúng 10 chữ số.";
  if (t[0] !== "0") return "Số điện thoại Việt Nam phải bắt đầu bằng số 0.";
  if (!PHONE_RE.test(t))
    return "Đầu số không hợp lệ (di động 03/05/07/08/09, cố định 02).";
  return null;
}

export function cccdError(v: string | null | undefined): string | null {
  const t = (v ?? "").trim();
  if (!t) return null;
  if (!CCCD_RE.test(t)) return "CCCD phải gồm đúng 12 chữ số.";
  // 3 số đầu = mã tỉnh khai sinh (001–096). Chặn rác kiểu 000.../111...
  const provinceCode = Number(t.slice(0, 3));
  if (provinceCode < 1 || provinceCode > 96)
    return "CCCD không hợp lệ (3 số đầu là mã tỉnh, 001–096).";
  return null;
}

// ===== Ngày sinh dd/mm/yyyy — có LOGIC LỊCH (không 30/2, 29/2 chỉ năm nhuận) =====

/** Số ngày tối đa của tháng m (1-12) trong năm y — đúng năm nhuận (29/2). */
export function daysInMonth(m: number, y: number): number {
  if (m === 2) return y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0) ? 29 : 28;
  return m === 4 || m === 6 || m === 9 || m === 11 ? 30 : 31;
}

/** Ghép d/m/y (chuỗi) → "yyyy-mm-dd"; thiếu bất kỳ phần nào → "". Không kiểm hợp lệ. */
export function dmyToIso(day: string, month: string, year: string): string {
  const d = (day ?? "").trim();
  const m = (month ?? "").trim();
  const y = (year ?? "").trim();
  if (!d || !m || !y) return "";
  return `${y.padStart(4, "0")}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
}

/**
 * Năm sinh (chế độ "Chỉ biết năm"). null = hợp lệ (hoặc CHƯA nhập); chuỗi = lỗi
 * nhỏ cạnh ô. `maxYear` = năm hiện tại (không cho năm tương lai).
 */
export function birthYearError(
  year: string,
  maxYear: number,
): string | null {
  const t = (year ?? "").trim();
  if (!t) return null;
  const y = Number(t);
  if (!Number.isInteger(y)) return "Năm sinh không hợp lệ.";
  if (y > maxYear) return "Năm sinh không thể ở tương lai.";
  if (y < 1900) return `Năm sinh không hợp lệ (1900–${maxYear}).`;
  return null;
}

/**
 * Kiểm ngày sinh dd/mm/yyyy. null = hợp lệ (hoặc CHƯA nhập gì — caller tự bắt
 * "bắt buộc"); chuỗi = lỗi nhỏ hiện cạnh ô.
 * - `maxIso` = hôm nay (yyyy-mm-dd): ngày sinh KHÔNG được sau hôm nay.
 * - Bắt 30/2, 31/4…, 29/2 chỉ năm nhuận; năm 1900..năm hiện tại.
 */
export function dobError(
  day: string,
  month: string,
  year: string,
  maxIso: string,
): string | null {
  const d = (day ?? "").trim();
  const m = (month ?? "").trim();
  const y = (year ?? "").trim();
  if (!d && !m && !y) return null; // chưa nhập gì
  if (!d || !m || !y) return "Nhập đủ ngày/tháng/năm.";
  const dd = Number(d);
  const mm = Number(m);
  const yy = Number(y);
  const curYear = Number(maxIso.slice(0, 4));
  if (!Number.isInteger(dd) || !Number.isInteger(mm) || !Number.isInteger(yy))
    return "Ngày/năm không hợp lệ.";
  // Năm tương lai nói thẳng là tương lai. Trước đây nó rơi chung vào câu
  // "Ngày/năm không hợp lệ.", nên gõ nhầm 2026 thành 2062 thì người trực phải tự
  // đoán sai ở đâu — trong khi dòng cuối hàm này đã có sẵn câu đúng cho trường
  // hợp y hệt (ngày trong tương lai của năm hiện tại).
  if (yy > curYear) return "Ngày sinh không thể ở tương lai.";
  if (yy < 1900) return `Năm sinh không hợp lệ (1900–${curYear}).`;
  if (mm < 1 || mm > 12) return "Ngày/năm không hợp lệ.";
  if (dd < 1 || dd > daysInMonth(mm, yy)) return "Ngày/năm không hợp lệ.";
  if (dmyToIso(d, m, y) > maxIso) return "Ngày sinh không thể ở tương lai.";
  return null;
}

// ===== Bản dùng cho ĐƯỜNG API (chuỗi ISO) =====
//
// TÌM ĐƯỢC KHI NGHIỆM THU 11/08/2026: `POST /api/patients` nhận ngày sinh
// **2099-01-01** và **1850-01-01**, tạo hồ sơ thật.
//
// Không phải vì thiếu luật — `dobError()` ngay phía trên đã chặn đúng cả hai từ
// lâu. Nó chỉ được nối vào ô nhập ba khung dd/mm/yyyy của form. Đường API nhận
// `date_of_birth` dạng chuỗi ISO và chuyển thẳng xuống, không đi qua luật nào.
//
// Đây là dạng lỗi lặp lại của dự án này: LUẬT ĐÚNG, KHÔNG NỐI VÀO ĐƯỜNG THẬT
// (xem thêm `doDetail()` trong lib/loi-api.ts — cùng một hình dạng, cùng một ngày).
// Nên bản này KHÔNG chép lại luật; nó tách chuỗi rồi gọi chính `dobError()`.

/** Ngày sinh dạng "yyyy-mm-dd" từ API. null = hợp lệ (hoặc bỏ trống). */
export function dobErrorIso(
  iso: string | null | undefined,
  maxIso: string,
): string | null {
  const t = (iso ?? "").trim();
  if (!t) return null;
  const khop = /^(\d{4})-(\d{2})-(\d{2})$/.exec(t);
  if (!khop) return "Ngày sinh không hợp lệ (cần dạng yyyy-mm-dd).";
  const [, y, m, d] = khop;
  return dobError(d, m, y, maxIso);
}

/** Hôm nay ở giờ Việt Nam, dạng "yyyy-mm-dd" — mốc "không thể ở tương lai". */
export function homNayVn(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

// Tên dài nhất từng gặp trong dữ liệu thật là 41 ký tự. 120 cho thoải mái mà vẫn
// chặn được rác — API từng nhận một cái tên 5000 ký tự và lưu xuống DB.
export const TEN_TOI_DA = 120;

/**
 * Kiểm họ tên. null = hợp lệ; chuỗi = lỗi.
 *
 * Chặn `<` `>` không phải vì React sẽ hiện ra mã (React tự thoát ký tự, đã kiểm)
 * — mà vì tên có thẻ HTML là dữ liệu rác sẽ đi tiếp vào phiếu in, tin nhắn, file
 * xuất Excel, những nơi KHÔNG tự thoát. Chặn ở cửa vào rẻ hơn vá từng nơi ra.
 */
export function tenError(v: string | null | undefined): string | null {
  const t = (v ?? "").trim();
  if (!t) return "Phải nhập họ tên.";
  if (t.length > TEN_TOI_DA)
    return `Họ tên quá dài (tối đa ${TEN_TOI_DA} ký tự).`;
  if (/[<>]/.test(t)) return "Họ tên chứa ký tự không hợp lệ.";
  if (/[\u0000-\u001f\u007f]/.test(t))
    return "Họ tên chứa ký tự không hợp lệ.";
  return null;
}
