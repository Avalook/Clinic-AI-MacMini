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

export interface ClinicHours {
  /** "HH:MM" */
  open: string;
  close: string;
}

export interface BookingPolicy {
  /** Độ dài 1 khung (phút). Luôn chia hết 60. */
  slotMinutes: number;
  /** Số chỗ kênh thường mỗi bác sĩ mỗi khung. */
  regularCap: number;
  /** Số chỗ vãng lai mỗi bác sĩ mỗi khung. */
  walkinCap: number;
  /**
   * Giờ mở cửa theo thứ, khoá "0"=CN … "6"=T7. Thứ vắng mặt = đóng cửa.
   *
   * ĐI CÙNG LUẬT, KHÔNG PHẢI HẰNG SỐ TRONG MÃ. Trước đây nó nằm ở hai file —
   * BookingHub (đóng lúc 22:00) và lib/roster.ts (23:00) — nên bác sĩ đăng ký
   * được ca 22:00–23:00 mà CSKH không đặt lịch vào được: một tiếng mỗi tối
   * biến mất giữa hai file. Và một hằng số trong bundle nghĩa là phòng khám
   * thứ hai không thể có giờ khác.
   */
  hours: Record<string, ClinicHours>;
}

interface PolicyResponse {
  slot_minutes?: unknown;
  regular_cap?: unknown;
  walkin_cap?: unknown;
  hours?: unknown;
}

/** Giờ mở cửa hợp lệ hay không — dữ liệu xấu ở đây là lưới vẽ sai giờ. */
function asHours(value: unknown): Record<string, ClinicHours> | null {
  if (typeof value !== "object" || value === null) return null;
  const out: Record<string, ClinicHours> = {};
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    if (typeof v !== "object" || v === null) return null;
    const { open, close } = v as { open?: unknown; close?: unknown };
    if (typeof open !== "string" || typeof close !== "string") return null;
    if (!/^\d{2}:\d{2}$/.test(open) || !/^\d{2}:\d{2}$/.test(close)) return null;
    out[k] = { open, close };
  }
  return out;
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
  if (!raw) {
    // Không đoán 15/2/1 (xem header file): lưới vẽ sai luật đúng lúc backend chết
    // là lúc nguy hiểm nhất. Trả null để người gọi nói thẳng là đọc không được.
    return null;
  }

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

  // Cùng lý do như ba con số trên: thiếu giờ mở cửa thì màn nói ra, không đoán.
  const hours = asHours(raw.hours);
  if (hours === null) return null;

  return { slotMinutes, regularCap, walkinCap, hours };
}

/**
 * MỘT luật số chỗ, như người vận hành đọc nó.
 *
 * Bên dưới có hai bảng (luật mãi mãi và luật có ngày) nhưng màn hình chỉ có
 * một danh sách. `kind` chỉ dùng để gọi đúng đường xoá — người dùng nhìn cột
 * "Áp dụng" chứ không nhìn tên tầng.
 */
export interface BookingRule {
  id: string;
  /** "standing" = mãi mãi, "temp" = có khoảng ngày. */
  kind: "standing" | "temp";
  /** null = áp cho mọi bác sĩ. */
  doctor_id: string | null;
  /** null = mọi thứ trong tuần. 0 = CN … 6 = T7. */
  weekday: number | null;
  /** Phút-trong-ngày, nửa mở [start, end). */
  minute_start: number;
  minute_end: number;
  regular_cap: number | null;
  walkin_cap: number | null;
  reason: string | null;
  /** Chỉ có với kind = "temp". */
  date_start: string | null;
  date_end: string | null;
  /**
   * Luật mãi mãi này đang bị một luật CÓ NGÀY phủ lên, nên hôm nay nó không
   * phải con số có hiệu lực. Backend tính sẵn: bắt giao diện tự suy ra thứ tự
   * ưu tiên là cách chắc chắn để hai nơi nói hai điều khác nhau.
   */
  shadowed: boolean;
}

/** Mọi luật còn hiệu lực của phòng khám, đã gộp hai tầng. */
export async function listBookingRules(): Promise<BookingRule[]> {
  const raw = await fetchFromBackend<{ items?: BookingRule[] }>(
    "/api/v1/booking-rules",
  );
  return raw?.items ?? [];
}
