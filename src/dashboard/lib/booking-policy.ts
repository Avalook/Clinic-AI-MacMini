// Luật đặt lịch của phòng khám đang đăng nhập, lấy từ backend (C.3).
//
// Trình duyệt KHÔNG đọc clinic.settings: A.5 đã bỏ cột đó khỏi GRANT cho
// `authenticated`, đúng vì nó từng chứa credential POS. Nguồn duy nhất là
// GET /api/v1/appointments/policy, và nó đọc cùng một hàng mà trigger
// enforce_slot_capacity đọc khi từ chối lịch.
//
// KHÔNG CÓ MẶC ĐỊNH Ở ĐÂY, VÀ ĐÓ LÀ CHỦ Ý. Một bộ 15/2/1 viết cứng để "đỡ khi
// backend chết" sẽ là bản sao thứ tư của luật, và nó sai đúng vào lúc nguy hiểm
// nhất: phòng khám khung 30 phút mà lưới vẽ 15 phút thì lễ tân bấm vào ô không
// tồn tại rồi nhận lỗi không giải thích được. Đọc không được thì màn nói thẳng
// là đọc không được — dù sao không có backend thì cũng không đặt được lịch.

import { fetchFromBackend } from "./backend-proxy";

export interface BookingPolicy {
  /** Độ dài 1 khung (phút). Luôn chia hết 60. */
  slotMinutes: number;
  /** Số chỗ kênh thường mỗi bác sĩ mỗi khung. */
  regularCap: number;
  /** Số chỗ vãng lai mỗi bác sĩ mỗi khung. */
  walkinCap: number;
}

interface PolicyResponse {
  slot_minutes?: unknown;
  regular_cap?: unknown;
  walkin_cap?: unknown;
}

function asInt(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) ? value : null;
}

/**
 * Đọc luật cho lần render này. `null` nghĩa là không đọc được — người gọi phải
 * hiển thị điều đó, không được tự đoán.
 */
export async function getBookingPolicy(): Promise<BookingPolicy | null> {
  const raw = await fetchFromBackend<PolicyResponse>("/api/v1/appointments/policy");
  if (!raw) return null;

  const slotMinutes = asInt(raw.slot_minutes);
  const regularCap = asInt(raw.regular_cap);
  const walkinCap = asInt(raw.walkin_cap);
  if (slotMinutes === null || regularCap === null || walkinCap === null) {
    return null;
  }
  // Backend đã chặn các giá trị này bằng CHECK constraint. Kiểm lại ở đây không
  // phải vì nghi ngờ backend, mà vì slotMinutes = 0 ở phía trình duyệt là một
  // phép chia cho 0 và một vòng lặp vẽ lưới không bao giờ dừng.
  if (slotMinutes < 1 || slotMinutes > 60 || 60 % slotMinutes !== 0) return null;
  if (regularCap < 1 || walkinCap < 0) return null;

  return { slotMinutes, regularCap, walkinCap };
}
