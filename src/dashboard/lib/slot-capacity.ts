// Luật chỗ mỗi khung (đặt lịch "rạp chiếu phim", 2026-07-02): mỗi BÁC SĨ ×
// KHUNG có một số chỗ cho lịch hẹn kênh thường (CSKH/Lễ tân đặt trước) và một
// số chỗ DÀNH RIÊNG khách vãng lai (booking_channel = WALK_IN). Hàng "Chưa phân
// bác sĩ" (doctor_id null) cũng bị giới hạn y hệt như một hàng riêng.
//
// C.3 — BA CON SỐ KHÔNG CÒN Ở ĐÂY. Trước đây file này giữ SLOT_MIN=15,
// REGULAR_CAP=2, WALKIN_CAP=1, và đó là bản sao thứ ba của cùng một luật (bản
// còn lại ở booking_service.py và ở trigger enforce_slot_capacity). Khi luật
// thành cấu hình của từng phòng khám, một bản sao viết cứng trong trình duyệt
// không còn là "trùng lặp vô hại" — nó là ô lưới vẽ sai chỗ so với ô mà
// database đếm, tức là lễ tân được mời đặt vào một khung không tồn tại.
//
// Giờ luật đi vào qua tham số: server đọc clinic.settings (GET
// /api/v1/appointments/policy) rồi truyền xuống. File vẫn THUẦN (không I/O).

import type { BookingPolicy } from "./booking-policy";

/** Trạng thái KHÔNG còn giữ chỗ (huỷ / không đến / bác sĩ từ chối chờ phân lại). */
export const DEAD_STATUSES = ["CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"] as const;

export function isDeadStatus(status?: string | null): boolean {
  return (DEAD_STATUSES as readonly string[]).includes((status ?? "").trim());
}

export function isWalkinChannel(channel?: string | null): boolean {
  return (channel ?? "").trim().toUpperCase() === "WALK_IN";
}

/** Độ dài 1 khung, tính bằng ms. */
export function slotMs(policy: BookingPolicy): number {
  return policy.slotMinutes * 60_000;
}

/** Mốc đầu khung chứa thời điểm iso (epoch ms). Độ dài khung buộc phải chia hết
 *  60' (backend từ chối giá trị khác), nên floor theo epoch UTC trùng khớp ranh
 *  giới khung giờ VN — lệch múi giờ là bội số giờ. */
export function slotBucketMs(iso: string, policy: BookingPolicy): number {
  const ms = slotMs(policy);
  return Math.floor(Date.parse(iso) / ms) * ms;
}

/** Các mốc phút hợp lệ trong 1 giờ ("00", "15", …) — dropdown phút của ô nhập
 *  giờ phải trùng đúng các cột lưới, nếu không lễ tân gõ được một giờ mà lưới
 *  không có ô và server sẽ dồn vào khung khác. */
export function slotMinuteOptions(policy: BookingPolicy): string[] {
  const out: string[] = [];
  for (let m = 0; m < 60; m += policy.slotMinutes) {
    out.push(String(m).padStart(2, "0"));
  }
  return out;
}

/** ISO UTC của [đầu khung, cuối khung) chứa iso — dùng cho query range server. */
export function slotBucketRange(
  iso: string,
  policy: BookingPolicy,
): { startUtc: string; endUtc: string } {
  const s = slotBucketMs(iso, policy);
  return {
    startUtc: new Date(s).toISOString(),
    endUtc: new Date(s + slotMs(policy)).toISOString(),
  };
}

export interface SlotApptLite {
  slot_start: string;
  doctor_id: string | null;
  booking_channel?: string | null;
  status?: string | null;
}

export interface SlotUsage {
  /** Số lịch kênh thường (chiếm chỗ đặt trước). */
  regular: number;
  /** Số lịch vãng lai (chiếm chỗ để dành). */
  walkin: number;
}

/** Key gộp: bác sĩ (null → "") + đầu khung. */
export function usageKey(
  doctorId: string | null | undefined,
  bucketMs: number,
): string {
  return `${doctorId ?? ""}|${bucketMs}`;
}

/** Gom danh sách lịch (đã bỏ/giữ nguyên trạng thái từ API) thành bảng chiếm chỗ
 *  theo (bác sĩ, khung). Tự bỏ các trạng thái chết — API GET hiện đã lọc
 *  CANCELLED/NO_SHOW nhưng còn trả DOCTOR_DECLINED, nên vẫn phải lọc lại ở đây. */
export function buildSlotUsage(
  appts: SlotApptLite[],
  policy: BookingPolicy,
): Map<string, SlotUsage> {
  const ms = slotMs(policy);
  const m = new Map<string, SlotUsage>();
  for (const a of appts) {
    if (!a.slot_start || isDeadStatus(a.status)) continue;
    const t = Date.parse(a.slot_start);
    if (!Number.isFinite(t)) continue;
    const key = usageKey(a.doctor_id, Math.floor(t / ms) * ms);
    const u = m.get(key) ?? { regular: 0, walkin: 0 };
    if (isWalkinChannel(a.booking_channel)) u.walkin += 1;
    else u.regular += 1;
    m.set(key, u);
  }
  return m;
}

export function usageAt(
  usage: Map<string, SlotUsage>,
  doctorId: string | null | undefined,
  bucketMs: number,
): SlotUsage {
  return usage.get(usageKey(doctorId, bucketMs)) ?? { regular: 0, walkin: 0 };
}
