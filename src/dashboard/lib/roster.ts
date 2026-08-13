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
  { key: "LE_TAN", label: "Lễ tân (Tiếp đón + thu ngân)", short: "Lễ tân", group: "Tầng 1", floor: "Tầng 1 (không Siêu âm)" },
  { key: "LAY_MAU", label: "Lấy máu", short: "Lấy máu", group: "Tầng 1", floor: "Tầng 1 (không Siêu âm)" },
  { key: "PHU_BS_KHAM", label: "Phụ BS (khám + thuốc) / Chạy ngoài", short: "Phụ BS / Chạy ngoài", group: "Tầng 1", floor: "Tầng 1 (không Siêu âm)" },
  { key: "TLYK", label: "Trợ lý y khoa (Đánh máy + Phụ khám)", short: "Trợ lý y khoa", group: "Tầng 1", floor: "Tầng 1 (không Siêu âm)" },
  { key: "PHU_BS_SA", label: "Phụ BS (khám + thuốc) + đánh SÂ", short: "Phụ BS + đánh SÂ", group: "Tầng 2", floor: "Tầng 2 · Khám Sản E10 + Monitoring" },
  { key: "PHONG_NGOAI_MOR", label: "Phòng ngoài + Phòng Monitoring (MÁY 730)", short: "Phòng ngoài + Monitoring", group: "Tầng 2", floor: "Tầng 4" },
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
//
// KHOÁ PHẢI LÀ CHUỖI `floor` THẬT trong STATIONS ở trên. Bản trước viết tắt
// ("Tầng 1 (ko SÂ)", "Tầng 2 · Khám Sản E10 + Mor") nên hai tầng ấy không bao
// giờ khớp và rơi về màu mặc định — một bảng màu hỏng một nửa mà không ai thấy,
// vì không có lỗi nào để thấy.
export const FLOOR_BORDER: Record<string, string> = {
  "Thủ thuật ngoài giờ": "border-t-specialty-andro",
  "HSS + Thủ thuật trong giờ": "border-t-specialty-andro",
  "Tầng 1 (không Siêu âm)": "border-t-specialty-service",
  "Tầng 2 · Khám Sản E10 + Monitoring": "border-t-success",
  "Tầng 4": "border-t-warning",
  "Tầng 4 phòng trong": "border-t-brand-600",
};

export const STATION_LABEL: Record<string, string> = Object.fromEntries(
  STATIONS.map((s) => [s.key, s.label]),
);




// ===== HAI HÀNG CON MỖI NGÀY =====
//
// File Excel "BẢNG LÀM VIỆC" (sheet LLV) dành HAI dòng cho mỗi ngày, và hai
// dòng ấy KHÔNG phải ca sáng / ca chiều — mỗi dòng là MỘT NGƯỜI.
//
//   Quang, 09/08/2026: *"có nghĩa là ngày hôm ấy có 2 bác sĩ trực, giờ sáng hay
//   chiều thì chi tiết trong trang nhỏ hiện ra lúc ấn vào dấu cộng"*.
//
// Đoán nhầm chỗ này là dựng cả cái bảng cho một mô hình sai: nếu hai hàng là
// hai CA thì một bác sĩ trực cả ngày phải nằm ở cả hai hàng, và cột "số bác sĩ
// trực" luôn đếm gấp đôi.

/** Chia phân công của một ô thành ĐÚNG hai hàng con: người đầu ở hàng trên,
 *  phần còn lại dồn xuống hàng dưới.
 *
 *  Dồn chứ không cắt bớt — Excel cũng viết "Thư/Hà Vũ" chung một ô khi ngày đó
 *  có ba người. Cắt mất người thứ ba nghĩa là bảng nói dối về ai đang trực. */
export function chiaHaiHang<T>(list: T[]): [T[], T[]] {
  return list.length <= 1 ? [list, []] : [[list[0]], list.slice(1)];
}

/** Số bác sĩ trực của một ngày = số NGƯỜI khác nhau ở trạm Lịch khám.
 *
 *  Đếm theo người, không theo dòng: một bác sĩ trực cả sáng lẫn chiều là HAI
 *  dòng `work_roster` nhưng vẫn là MỘT bác sĩ. Cột này trong Excel do quản lý
 *  gõ tay; ở đây nó được TÍNH RA, nên không thể lệch với các ô bên cạnh. */
export function demBacSiTruc(
  rows: {
    work_date: string;
    station: string;
    staff_id?: string | null;
    staff_name?: string | null;
  }[],
  date: string,
): number {
  const nguoi = new Set<string>();
  for (const r of rows) {
    if (r.work_date !== date || r.station !== "LICH_KHAM") continue;
    const khoa = r.staff_id ?? r.staff_name;
    if (khoa) nguoi.add(khoa);
  }
  return nguoi.size;
}

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

/** Thứ 2 của tuần chứa `d`. Chỉ dùng nội bộ, với Date đã chắc chắn hợp lệ. */
function mondayOfUtc(d: Date): string {
  const dow = d.getUTCDay(); // 0=CN
  const diff = dow === 0 ? -6 : 1 - dow; // về thứ 2
  const monday = new Date(d);
  monday.setUTCDate(d.getUTCDate() + diff);
  return toISO(monday);
}

/**
 * Thứ 2 của tuần chứa `dateStr` (yyyy-mm-dd). `null` = `dateStr` không đọc được.
 *
 * TRẢ `null` CHỨ KHÔNG NÉM, VÌ CHUỖI NÀY ĐẾN TỪ THANH ĐỊA CHỈ. `/home?weekAppt=…`
 * và `/schedule?week=…` lấy thẳng tham số URL rồi đưa vào đây. Bản cũ dựng
 * `new Date("abcT00:00:00Z")` thành Invalid Date, đi tiếp bình thường, rồi
 * `toISO()` gọi `toISOString()` — và CHÍNH `toISOString()` là thứ ném
 * `RangeError: Invalid time value`. Server component ném thì cả TRANG CHỦ rơi
 * vào error.tsx: một link hỏng hay một lần sửa tay trên thanh địa chỉ là màn
 * hình đầu ngày của mọi nhân viên không mở được.
 *
 * ĐÂY LÀ CON THỨ BA CÙNG MỘT HỌ. Hai lần trước (`/api/roster?date=99-99-9999`,
 * và `/api/appointments` thiếu `date`) đều được vá TẠI CHỖ NÓ NỔ, nên bản dùng
 * chung trong lib này sống sót qua cả hai lần — và nó phục vụ trang chủ. Luật
 * rút ra: hàm nhận ngày từ người dùng phải trả giá trị rỗng thay vì ném, và chỗ
 * kiểm phải nằm ở BIÊN (nơi chuỗi đi vào), không rải rác ở từng nơi gọi.
 *
 * `mondayOfUtc` bên dưới vẫn ném nếu bị đưa Date hỏng — cố ý: tới đó thì đó là
 * lỗi lập trình, không phải dữ liệu người dùng, và im lặng trả sai còn tệ hơn.
 */
export function weekStartOf(dateStr: string): string | null {
  const d = new Date(dateStr + "T00:00:00Z");
  if (Number.isNaN(d.getTime())) return null;
  return mondayOfUtc(d);
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
  // Đi thẳng vào `mondayOfUtc`: ngày này do chính hàm dựng nên luôn hợp lệ, nên
  // không phải xử lý một `null` không bao giờ xảy ra ở mọi nơi gọi.
  return mondayOfUtc(nowVn);
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
