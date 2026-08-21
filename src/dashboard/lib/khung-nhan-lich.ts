// Khung GIỜ NHẬN LỊCH của phòng khám theo thứ — đọc từ API, dùng để lọc ô giờ.
//
// VÌ SAO TÁCH RIÊNG KHỎI booking-policy.ts: file kia `import` proxy gọi backend,
// nên nạp nó vào bài kiểm là kéo theo cả tầng mạng. Phần dưới đây thuần tính
// toán, không phụ thuộc gì, nên kiểm được thẳng.
//
// GIỜ MỞ CỬA KHÔNG PHẢI GIỜ NHẬN LỊCH. Cửa mở 07:00–22:00 nhưng ba ca chỉ phủ
// 08:00–21:30; ba khoảng còn lại — trước ca sáng, nghỉ trưa, sau ca tối —
// backend TỪ CHỐI (21/08/2026). Trình duyệt lọc theo đây để không mời rồi mới
// mắng; backend vẫn là chốt cứng.
//
// KHÔNG quy đổi "17:30" ra phút ở đây: việc ấy là LUẬT và đã có bản Python
// (core/shifts.py). Backend gửi sang phút sẵn; một bản thứ hai bằng TypeScript
// sẽ lỡ mất lần sửa sau, đúng như giờ đóng cửa từng lệch giữa hai file.

/** thứ ("0"=CN … "6"=T7) → các khoảng [phút đầu, phút cuối), nửa mở. */
export type KhungNhanLich = Record<string, [number, number][]>;

/** Dữ liệu lạ ⇒ `{}` = "chưa biết", và "chưa biết" thì KHÔNG chặn gì. */
export function docKhungNhanLich(value: unknown): KhungNhanLich {
  if (typeof value !== "object" || value === null) return {};
  const out: KhungNhanLich = {};
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    if (!Array.isArray(v)) return {};
    const cap: [number, number][] = [];
    for (const w of v) {
      if (!Array.isArray(w) || w.length !== 2) return {};
      const [lo, hi] = w as unknown[];
      if (typeof lo !== "number" || typeof hi !== "number") return {};
      if (!Number.isInteger(lo) || !Number.isInteger(hi) || hi <= lo) return {};
      cap.push([lo, hi]);
    }
    out[k] = cap;
  }
  return out;
}

/**
 * Phút này có nằm trong khung nhận lịch của thứ đó không.
 *
 * Không biết thì trả `true`. Hỏi hụt mà chặn là khoá sạch lưới vì một lần mạng
 * lỗi; backend vẫn còn chốt cứng ở dưới nên sai theo hướng này chỉ mất một lần
 * bấm.
 */
export function trongKhungNhanLich(
  khung: KhungNhanLich | undefined,
  weekday: number,
  phut: number,
): boolean {
  const cap = khung?.[String(weekday)];
  if (!cap || cap.length === 0) return true;
  return cap.some(([lo, hi]) => phut >= lo && phut < hi);
}

/** Thứ (0=CN…6=T7) của một ngày "YYYY-MM-DD" theo lịch địa phương. */
export function thuCuaNgay(isoDate: string): number {
  return new Date(`${isoDate}T00:00:00`).getDay();
}
