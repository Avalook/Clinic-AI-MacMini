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

// 29/09/2026 — PHẦN ĐẾM GHẾ ĐÃ BỎ KHỎI ĐÂY. `buildSlotUsage`/`usageAt` tự cộng
// lịch trong ngày rồi màn hình so với TRẦN CHUNG (`policy.regularCap`), trong
// khi trigger chặn theo bác sĩ × khung có luật riêng — lưới mời ghế máy chủ từ
// chối, giấu ghế máy chủ còn nhận. Số ghế nay do máy chủ trả
// (`/api/appointments/luoi-ngay`, đọc qua lib/suc-chua-luoi.ts). Danh sách
// trạng thái "chết" cũng chỉ còn ở Python (core/trang_thai_lich.py). File này
// chỉ còn các phép chia khung THUẦN để hiển thị.

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
