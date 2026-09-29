// Đọc số ghế của lưới đặt chỗ TỪ MÁY CHỦ — hàm thuần, không I/O.
//
// VÌ SAO (29/09/2026, Tuyền: "sửa đi"). Lưới "rạp chiếu phim" và chữ "còn
// trống / đã kín" từng tự cộng lịch trong ngày (`buildSlotUsage`) rồi so với
// TRẦN CHUNG của phòng khám (`policy.regularCap/walkinCap`). Trigger chặn theo
// `resolve_effective_cap` — theo BÁC SĨ × KHUNG, có luật riêng. Hạ BS X 18:00
// xuống 1 chỗ thì lưới vẫn mời ghế 2 rồi máy chủ báo đầy; nâng lên 4 thì lưới
// chỉ vẽ 2 ghế. Lịch chưa gán bác sĩ và tuần chưa công bố (trigger miễn kiểm)
// cũng bị lưới khoá oan.
//
// Nay `GET /api/appointments/luoi-ngay` trả sẵn `regular_cap/used`,
// `walkin_cap/used` từng khung cho từng bác sĩ, cùng cờ trần có CHẶN không.
// File này chỉ tra các con số ấy. Không có hằng số nào của luật ở đây.

/** Một khung của một hàng bác sĩ — y hình `CapacityService.quote().slots[]`. */
export interface KhungSucChua {
  time: string;
  minute_of_day: number;
  slot_minutes: number;
  regular_cap: number;
  walkin_cap: number;
  regular_used: number;
  walkin_used: number;
  con_lai: number;
  state: string;
}

/** Một hàng của lưới = `quote()` của một bác sĩ (doctor_id null = chưa phân). */
export interface HangSucChua {
  doctor_id: string | null;
  closed: boolean;
  off_duty: boolean;
  roster_week_published: boolean;
  dat_tu_do?: boolean;
  /** Trần LỊCH HẸN có chặn không (false: chưa gán bác sĩ / tuần chưa công bố). */
  regular_chan: boolean;
  /** Trần TRỰC TIẾP có chặn không (trigger luôn kiểm). */
  walkin_chan: boolean;
  shift_windows: [number, number][];
  slots: KhungSucChua[];
}

export interface SucChuaNgay {
  date: string;
  hang: HangSucChua[];
}

export type LoaiGhe = "regular" | "walkin";

/** Hàng của một bác sĩ ("" / null = hàng chưa phân bác sĩ). null = máy chủ
 *  chưa trả hàng này (đang tải, hoặc bác sĩ không nằm trong lượt hỏi). */
export function hangCua(
  sc: SucChuaNgay | null | undefined,
  doctorId: string | null | undefined,
): HangSucChua | null {
  if (!sc) return null;
  const id = doctorId || null;
  return sc.hang.find((h) => (h.doctor_id || null) === id) ?? null;
}

/** Khung chứa phút này (nửa mở [đầu, đầu + độ dài)). null = máy chủ không có
 *  khung nào ở đây — ngoài ca trực / ngoài giờ nhận lịch. */
export function khungChua(
  hang: HangSucChua | null | undefined,
  phut: number,
): KhungSucChua | null {
  if (!hang || !Number.isFinite(phut)) return null;
  return (
    hang.slots.find(
      (k) => phut >= k.minute_of_day && phut < k.minute_of_day + k.slot_minutes,
    ) ?? null
  );
}

export function daDung(k: KhungSucChua, loai: LoaiGhe): number {
  return loai === "walkin" ? k.walkin_used : k.regular_used;
}

export function tran(k: KhungSucChua, loai: LoaiGhe): number {
  return loai === "walkin" ? k.walkin_cap : k.regular_cap;
}

function coChan(hang: HangSucChua, loai: LoaiGhe): boolean {
  return loai === "walkin" ? hang.walkin_chan : hang.regular_chan;
}

/** Số ghế VẼ cho khung. Trần chặn → đúng bằng trần. Trần KHÔNG chặn (trigger
 *  miễn kiểm) → luôn chừa một ghế trống sau người cuối, để đặt vượt được như
 *  máy chủ cho phép. */
export function soGhe(hang: HangSucChua, k: KhungSucChua, loai: LoaiGhe): number {
  const t = Math.max(tran(k, loai), 0);
  return coChan(hang, loai) ? t : Math.max(t, daDung(k, loai) + 1);
}

/** Số hàng ghế cần vẽ cho một bác sĩ trên các cột phút đang hiện = ghế nhiều
 *  nhất của một khung. Khung ít ghế hơn thì các ô thừa là "không có ghế". */
export function soHangGhe(
  hang: HangSucChua | null | undefined,
  loai: LoaiGhe,
  cacPhut: number[],
): number {
  if (!hang) return 0;
  let n = 0;
  for (const p of cacPhut) {
    const k = khungChua(hang, p);
    if (k) n = Math.max(n, soGhe(hang, k, loai));
  }
  return n;
}

/** Khung ở phút này đã hết ghế loại này chưa — THEO MÁY CHỦ.
 *  true = đầy (máy chủ sẽ từ chối); false = còn; null = không biết / không có
 *  khung (đừng nói "còn trống" khi chưa có số). */
export function khungDay(
  hang: HangSucChua | null | undefined,
  phut: number,
  loai: LoaiGhe,
): boolean | null {
  const k = khungChua(hang, phut);
  if (!hang || !k) return null;
  if (!coChan(hang, loai)) return false;
  return daDung(k, loai) >= tran(k, loai);
}

/** "HH:mm" → phút trong ngày; chuỗi hỏng → NaN (không ném). */
export function phutCua(hhmm: string): number {
  const m = /^(\d{1,2}):(\d{2})$/.exec((hhmm ?? "").trim());
  if (!m) return Number.NaN;
  return Number(m[1]) * 60 + Number(m[2]);
}
