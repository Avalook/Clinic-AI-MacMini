// "CÒN CHỖ" — kiểu dữ liệu + cách gọi, dùng chung cho mọi màn đặt lịch.
//
// Tuyền duyệt 16/09/2026: MỘT nguồn còn chỗ ở backend. Bảng Bác sĩ × tuần
// (`/appointments/cho-trong-tuan`) và popup / lưới khung giờ (`/appointments/
// quote`) đều do `capacity_service.py` tính; ô tuần tóm từ chính quote của ngày
// ấy. File này KHÔNG tính sức chứa — chỉ gọi và đặt nhãn.

export type TrangThaiNgay =
  | "CON_CHO"
  | "IT_CHO"
  | "DAY"
  | "NGHI"
  | "DONG_CUA"
  | "TU_DO"
  | "DA_QUA";

export interface ONgay {
  date: string;
  trang_thai: TrangThaiNgay;
  da_dat: number;
  con_cho: number | null;
  tong_cho: number | null;
}

export interface HangBacSi {
  /** null = hàng "Chưa phân bác sĩ". */
  id: string | null;
  full_name: string;
  role: string | null;
  o: ONgay[];
}

export interface BangTuan {
  week_start: string;
  ngay: string[];
  bac_si: HangBacSi[];
}

export interface KhungQuote {
  time: string;
  minute_of_day: number;
  slot_minutes: number;
  regular_cap: number;
  regular_used: number;
  con_lai: number;
  state: "free" | "few" | "full" | "closed";
}

export interface QuoteNgay {
  date: string;
  closed: boolean;
  off_duty: boolean;
  dat_tu_do: boolean;
  slots: KhungQuote[];
}

export const NHAN_NGAY: Record<TrangThaiNgay, string> = {
  CON_CHO: "Còn chỗ",
  IT_CHO: "Ít chỗ",
  DAY: "Đã đầy",
  NGHI: "Nghỉ",
  DONG_CUA: "Đóng cửa",
  TU_DO: "Đặt tự do",
  DA_QUA: "Đã qua",
};

/** Lớp màu theo trạng thái — một bảng cho mọi ô/chú thích. */
export const MAU_NGAY: Record<TrangThaiNgay, string> = {
  CON_CHO: "bg-success-bg text-success",
  IT_CHO: "bg-warning-bg text-warning",
  DAY: "bg-danger-bg text-danger",
  NGHI: "bg-surface-sunken text-ink-muted",
  DONG_CUA: "bg-surface-sunken text-ink-faint",
  TU_DO: "bg-brand-50 text-brand-700",
  DA_QUA: "bg-surface-muted text-ink-faint",
};

/** Ô ngày có mở được popup chọn giờ không. */
export function moDuoc(o: ONgay): boolean {
  return !["NGHI", "DONG_CUA", "DA_QUA"].includes(o.trang_thai);
}

/** Chữ trong ô ngày. Đặt tự do thì không in "/N" như một giới hạn. */
export function chuONgay(o: ONgay): string {
  if (o.trang_thai === "TU_DO") return o.da_dat ? `Tự do · ${o.da_dat}` : "Tự do";
  if (o.trang_thai === "CON_CHO" || o.trang_thai === "IT_CHO") return `Còn ${o.con_cho}`;
  return NHAN_NGAY[o.trang_thai];
}

/** Chữ + khoá của một khung giờ trong popup / lưới. */
export function chuKhung(
  k: KhungQuote,
  datTuDo: boolean,
  daQua: boolean,
): { chu: string; khoa: boolean; mau: string } {
  if (daQua) return { chu: "Đã qua", khoa: true, mau: "bg-surface-muted text-ink-faint" };
  if (datTuDo) {
    return {
      chu: k.regular_used ? `${k.regular_used} đã đặt` : "Đặt tự do",
      khoa: false,
      mau: "bg-brand-50 text-brand-700",
    };
  }
  if (k.con_lai <= 0) return { chu: "Đã đầy", khoa: true, mau: "bg-danger-bg text-danger" };
  return {
    chu: `Còn ${k.con_lai} chỗ`,
    khoa: false,
    mau: k.state === "few" ? "bg-warning-bg text-warning" : "bg-success-bg text-success",
  };
}

/** Thứ Hai của tuần chứa `iso` (yyyy-mm-dd, giờ VN), lệch `offset` tuần. */
export function thuHaiCua(iso: string, offset = 0): string {
  const d = new Date(`${iso}T12:00:00+07:00`);
  const thu = (d.getUTCDay() + 6) % 7; // T2 = 0
  d.setUTCDate(d.getUTCDate() - thu + offset * 7);
  return d.toISOString().slice(0, 10);
}

/** Phút trong ngày (giờ VN) của mốc ms — khoá khung đã qua của hôm nay. */
export function phutVn(ms: number): number {
  const [h, m] = new Date(ms)
    .toLocaleTimeString("en-GB", {
      timeZone: "Asia/Ho_Chi_Minh",
      hour: "2-digit",
      minute: "2-digit",
    })
    .split(":");
  return Number(h) * 60 + Number(m);
}

export async function taiBangTuan(weekStart: string, signal?: AbortSignal): Promise<BangTuan | null> {
  const r = await fetch(`/api/appointments/cho-trong-tuan?week_start=${weekStart}`, { signal }).catch(
    () => null,
  );
  return r && r.ok ? ((await r.json()) as BangTuan) : null;
}

export async function taiQuote(
  date: string,
  doctorId: string | null,
  signal?: AbortSignal,
): Promise<QuoteNgay | null> {
  const r = await fetch(
    `/api/appointments/quote?date=${date}${doctorId ? `&doctor_id=${doctorId}` : ""}`,
    { signal },
  ).catch(() => null);
  return r && r.ok ? ((await r.json()) as QuoteNgay) : null;
}
