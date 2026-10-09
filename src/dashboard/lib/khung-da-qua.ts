// KHUNG GIỜ "ĐÃ QUA" — một luật cho mọi màn đặt / đổi lịch (09/10/2026).
//
// Phòng khám: "BN đến 17:25, slot còn trống, ca kết thúc 17:30 mà báo 'Không
// thể đặt lịch trong quá khứ'". Máy chủ vốn đúng — `booking_service.
// _chan_dat_vao_qua_khu(slot_end)` chỉ chặn khi GIỜ KẾT THÚC ≤ bây giờ; khung
// 17:15–17:30 lúc 17:25 vẫn đang chạy. Màn hình lại so GIỜ BẮT ĐẦU nên chặn oan.
// Tuyền: "luật trước bị cứng, giờ cho đặt".
//
// Chỉ là luật thời gian. Giờ mở cửa, ngoài khung ca (`_chan_dat_ngoai_khung_ca`)
// và sức chứa vẫn ở máy chủ, KHÔNG đổi: ca hết thì vẫn bị chặn.
//
// Đầu vào rác KHÔNG ném. Không biết giờ bắt đầu / bây giờ → "chưa qua" (máy chủ
// chốt lại lúc ghi). Không biết độ dài khung → coi như 0 phút, tức quay về so
// giờ bắt đầu — chặt hơn, không bao giờ mở rộng thêm.

import { vnLocalToUtcISO } from "./datetime.ts";

function soHuuHan(x: unknown): number | null {
  return typeof x === "number" && Number.isFinite(x) ? x : null;
}

function soPhut(soPhutKhung: unknown): number {
  const n = soHuuHan(soPhutKhung);
  return n !== null && n > 0 ? n : 0;
}

/** Mốc ms của giờ bắt đầu: số ms, chuỗi ISO, hoặc Date. Rác → null. */
function moc(batDau: unknown): number | null {
  if (batDau instanceof Date) return soHuuHan(batDau.getTime());
  if (typeof batDau === "string" && batDau.trim() !== "") return soHuuHan(Date.parse(batDau));
  return soHuuHan(batDau);
}

/** Khung bắt đầu `batDau`, dài `soPhutKhung` phút, đã qua lúc `bayGio` (ms)
 *  chưa — tức giờ KẾT THÚC ≤ bây giờ. Biên đúng phút: kết thúc 17:30, bây giờ
 *  17:30:00 → đã qua (cùng `slot_end <= now` của máy chủ). */
export function khungDaQua(batDau: unknown, soPhutKhung: unknown, bayGio: unknown): boolean {
  const dau = moc(batDau);
  const nay = soHuuHan(bayGio);
  if (dau === null || nay === null) return false;
  return dau + soPhut(soPhutKhung) * 60_000 <= nay;
}

/** Cùng luật, đơn vị PHÚT TRONG NGÀY (lưới khung giờ của một ngày, giờ VN). */
export function khungDaQuaTheoPhut(
  phutBatDau: unknown,
  soPhutKhung: unknown,
  phutBayGio: unknown,
): boolean {
  const dau = soHuuHan(phutBatDau);
  const nay = soHuuHan(phutBayGio);
  if (dau === null || nay === null) return false;
  return dau + soPhut(soPhutKhung) <= nay;
}

/** Cùng luật cho ô Ngày + Giờ người dùng chọn ("2026-10-09", "17:15", giờ VN). */
export function khungDaQuaVn(
  ngay: unknown,
  gio: unknown,
  soPhutKhung: unknown,
  bayGio: unknown,
): boolean {
  if (typeof ngay !== "string" || typeof gio !== "string") return false;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(ngay) || !/^\d{2}:\d{2}$/.test(gio)) return false;
  let iso: string;
  try {
    iso = vnLocalToUtcISO(ngay, gio);
  } catch {
    return false; // "2026-13-40" — ngày không có thật
  }
  return khungDaQua(iso, soPhutKhung, bayGio);
}
