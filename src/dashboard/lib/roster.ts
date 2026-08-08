// Lịch làm việc (weekly roster) — cấu hình phòng/trạm + helper ngày/tuần.
// Danh sách trạm suy ra từ bảng Google Sheet của phòng khám; chỉnh ở đây nếu
// phòng khám đổi cách phân công.


// Cookie lưu "tôi là ai" cho vai trò không phải bác sĩ (lọc lịch cá nhân).
export const ROSTER_STAFF_COOKIE = "roster_staff_id";

export interface Station {
  key: string;
  label: string; // tên đầy đủ (tooltip / editor)
  short: string; // nhãn cột ngắn trên bảng
  group: string; // nhóm MÀU (giữ cho schedule kanban + chip trang chủ)
  floor: string; // nhãn TẦNG để gom header bảng "Lịch làm việc" (đúng file Excel)
}

// Thứ tự cột = thứ tự cột trong file "BẢNG LÀM VIỆC" (sheet LLV): Lịch khám →
// Thủ thuật ngoài giờ → HSS → Tầng 1 → Tầng 2 → Tầng 4 → Tầng 4 phòng trong.
// `floor` rỗng = cột đứng riêng (Lịch khám), không thuộc tầng nào.
export const STATIONS: Station[] = [
  { key: "LICH_KHAM", label: "Lịch khám (Bác sĩ)", short: "Lịch khám", group: "Bác sĩ", floor: "" },
  { key: "SB_CHIEU", label: "SB - Chiều", short: "SB - Chiều", group: "Ngoài giờ", floor: "Thủ thuật ngoài giờ" },
  { key: "THU_THUAT_NGOAI_GIO", label: "Thủ thuật ngoài giờ", short: "Thủ thuật NG", group: "Ngoài giờ", floor: "Thủ thuật ngoài giờ" },
  { key: "HSS_THU_THUAT", label: "HSS + Thủ thuật trong giờ", short: "HSS / Thủ thuật", group: "Ngoài giờ", floor: "HSS + Thủ thuật trong giờ" },
  { key: "LE_TAN", label: "Lễ tân (Tiếp đón + thu ngân)", short: "Lễ tân", group: "Tầng 1", floor: "Tầng 1 (ko SÂ)" },
  { key: "LAY_MAU", label: "Lấy máu", short: "Lấy máu", group: "Tầng 1", floor: "Tầng 1 (ko SÂ)" },
  { key: "PHU_BS_KHAM", label: "Phụ BS (khám + thuốc) / Chạy ngoài", short: "Phụ BS / Chạy ngoài", group: "Tầng 1", floor: "Tầng 1 (ko SÂ)" },
  { key: "TLYK", label: "TLYK (Đánh máy + Phụ khám)", short: "TLYK", group: "Tầng 1", floor: "Tầng 1 (ko SÂ)" },
  { key: "PHU_BS_SA", label: "Phụ BS (khám + thuốc) + đánh SÂ", short: "Phụ BS + đánh SÂ", group: "Tầng 2", floor: "Tầng 2 · Khám Sản E10 + Mor" },
  { key: "PHONG_NGOAI_MOR", label: "Phòng ngoài + Phòng mor (MÁY 730)", short: "Phòng ngoài + mor", group: "Tầng 2", floor: "Tầng 4" },
  { key: "MAY_TRONG", label: "Máy trong E10 + VLTL/thủ thuật", short: "Máy trong E10", group: "Tầng 4", floor: "Tầng 4 phòng trong" },
  { key: "MAY_NGOAI", label: "Máy ngoài (N/A)", short: "Máy ngoài", group: "Tầng 4", floor: "Tầng 4 phòng trong" },
];

// Gom STATIONS thành các đoạn cùng TẦNG (giữ thứ tự) để dựng header 2 hàng:
// hàng trên = tên tầng (gộp cột), hàng dưới = tên trạm.
export interface FloorSegment {
  floor: string;
  stations: Station[];
}
export const STATION_SEGMENTS: FloorSegment[] = STATIONS.reduce<FloorSegment[]>(
  (segs, s) => {
    const last = segs[segs.length - 1];
    if (last && last.floor === s.floor) last.stations.push(s);
    else segs.push({ floor: s.floor, stations: [s] });
    return segs;
  },
  [],
);

// Màu nhấn theo TẦNG (viền trên header tầng cho dễ phân biệt khối).
export const FLOOR_COLOR: Record<string, string> = {
  "Thủ thuật ngoài giờ": "var(--color-specialty-andro)",
  "HSS + Thủ thuật trong giờ": "var(--color-specialty-andro)",
  "Tầng 1 (ko SÂ)": "var(--color-specialty-service)",
  "Tầng 2 · Khám Sản E10 + Mor": "var(--color-success)",
  "Tầng 4": "var(--color-warning)",
  "Tầng 4 phòng trong": "var(--color-brand-500)",
};

export const STATION_LABEL: Record<string, string> = Object.fromEntries(
  STATIONS.map((s) => [s.key, s.label]),
);

export const STATION_SHORT: Record<string, string> = Object.fromEntries(
  STATIONS.map((s) => [s.key, s.short]),
);

export const STATION_GROUP: Record<string, string> = Object.fromEntries(
  STATIONS.map((s) => [s.key, s.group]),
);

// Màu theo nhóm trạm (chấm/viền thẻ kanban).
export const GROUP_COLOR: Record<string, string> = {
  "Bác sĩ": "var(--color-brand-600)",
  "Tầng 1": "var(--color-specialty-service)",
  "Tầng 2": "var(--color-success)",
  "Tầng 4": "var(--color-warning)",
  "Ngoài giờ": "var(--color-specialty-andro)",
};

export type Shift = "FULL" | "SANG" | "CHIEU";
export const SHIFTS: Shift[] = ["FULL", "SANG", "CHIEU"];
export const SHIFT_LABEL: Record<Shift, string> = {
  FULL: "Cả ngày",
  SANG: "Sáng",
  CHIEU: "Chiều",
};

const WEEKDAY = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];

/** "Thứ 2".."Thứ 7" / "Chủ nhật" cho 1 ngày yyyy-mm-dd (tính UTC, roster là DATE). */
export function dayLabel(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00Z");
  const w = d.getUTCDay();
  return w === 0 ? "Chủ nhật" : `Thứ ${w + 1}`;
}

/** Nhãn ngắn T2..CN. */
export function dayShort(dateStr: string): string {
  return WEEKDAY[new Date(dateStr + "T00:00:00Z").getUTCDay()] ?? "";
}

/** dd/mm cho 1 ngày yyyy-mm-dd. */
export function fmtDayMonth(dateStr: string): string {
  const [, m, d] = dateStr.split("-");
  return `${d}/${m}`;
}

function toISO(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Thứ 2 của tuần chứa `dateStr` (yyyy-mm-dd). */
export function weekStartOf(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00Z");
  const dow = d.getUTCDay(); // 0=CN
  const diff = dow === 0 ? -6 : 1 - dow; // về thứ 2
  d.setUTCDate(d.getUTCDate() + diff);
  return toISO(d);
}

/** 7 ngày của tuần bắt đầu từ `weekStart` (T2..CN). */
export function weekDates(weekStart: string): string[] {
  const base = new Date(weekStart + "T00:00:00Z");
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(base);
    d.setUTCDate(base.getUTCDate() + i);
    return toISO(d);
  });
}

/** Tuần kế trước/sau (±7 ngày). */
export function shiftWeek(weekStart: string, weeks: number): string {
  const d = new Date(weekStart + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + weeks * 7);
  return toISO(d);
}

/** Thứ 2 của tuần hiện tại theo giờ VN (server chạy UTC). */
export function currentWeekStartVn(): string {
  const nowVn = new Date(Date.now() + 7 * 60 * 60 * 1000);
  return weekStartOf(nowVn.toISOString().slice(0, 10));
}

/** Hôm nay (yyyy-mm-dd) theo giờ VN. */
export function todayVn(): string {
  return new Date(Date.now() + 7 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

// ===== GIỜ MỞ CỬA PHÒNG KHÁM =====
//
// CẤU HÌNH, KHÔNG PHẢI HẰNG SỐ. File này từng trả cứng T2–T6 17:00–23:00 và
// cuối tuần 08:00–23:00, còn BookingHub trả 22:00 cho giờ đóng cửa. Hai nguồn,
// hai con số: bác sĩ đăng ký được ca 22:00–23:00 mà CSKH không đặt lịch vào
// được, và không có lỗi nào chỉ ra điều đó.
//
// Giờ cả hai đọc `clinic.settings.hours` (migration 20260803000011), truyền
// vào qua BookingPolicy. `hours` là bắt buộc — không có tham số mặc định, vì
// một mặc định ở đây chính là cách hai con số cũ sống sót lâu như vậy.
export type { ClinicHours } from "./booking-policy";
import type { ClinicHours } from "./booking-policy";

/** Giờ mở cửa của một ngày; `null` = phòng khám đóng cửa hôm đó. */
export function clinicHoursForDate(
  isoDate: string,
  hours: Record<string, ClinicHours>,
): ClinicHours | null {
  const dow = new Date(isoDate + "T00:00:00Z").getUTCDay(); // 0=CN, 6=T7
  const today = hours[String(dow)];
  if (!today || today.open === today.close) return null;
  return today;
}

/**
 * Kiểm giờ hẹn có nằm trong giờ mở cửa của NGÀY đó không. null = hợp lệ.
 * So sánh chuỗi "HH:MM" (cùng độ dài) là đủ. Giờ bắt đầu phải < giờ đóng cửa.
 */
export function clinicHoursError(
  isoDate: string,
  time: string,
  hours: Record<string, ClinicHours>,
): string | null {
  if (!isoDate || !time) return null;
  const today = clinicHoursForDate(isoDate, hours);
  if (!today) return "Phòng khám không làm việc ngày này.";
  if (time < today.open || time >= today.close) {
    // Câu cũ phân biệt "cuối tuần" với "T2–T6" — đúng với lịch Dr4Women và sai
    // với bất kỳ phòng khám nào chia lịch khác. Nói thẳng giờ của ĐÚNG ngày đó.
    return `Ngày này phòng khám nhận khám ${today.open}–${today.close}. Hãy chọn giờ trong khoảng này.`;
  }
  return null;
}

// ===== TRẠM HỢP LỆ THEO VAI TRÒ — ĐÃ CHUYỂN VÀO DATABASE =====
//
// `stationsForRole` và `defaultStationForRole` từng ở đây. Cả hai đã bỏ
// (20260809000002), vì hai lý do:
//
// 1. LUẬT CỦA CHÚNG SAI SO VỚI ĐỜI THẬT. `stationsForRole` nói: bác sĩ → đúng
//    một trạm, MỌI VAI CÒN LẠI → mười một trạm còn lại. Gọn tới mức không chặn
//    được gì: lễ tân chọn được "Máy trong E10 + VLTL/thủ thuật". Còn chiều
//    ngược lại thì quá chặt — lễ tân Dr4Women đi LẤY MÁU 234 ca trong lịch
//    thật, thứ mà `defaultStationForRole` không hề biết.
//
// 2. LỌC Ở TRÌNH DUYỆT KHÔNG PHẢI LÀ CHẶN. Một lời gọi API tự chế không đi qua
//    hàm này. Backend mới là nơi từ chối (`RosterService._kiem_pham_vi_tram`).
//
// Nay hỏi `GET /api/roster?staff_id=…`, trả lời lấy từ bảng
// `vai_duoc_vao_tram` — cùng bảng mà backend dùng để từ chối, nên giao diện
// không thể mời một vị trí rồi lưu mới báo lỗi. Ma trận gieo từ chính lịch trực
// của phòng khám và quản lý sửa được.
