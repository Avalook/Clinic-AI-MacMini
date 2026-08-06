// Clinic time is Vietnam time (GMT+7, Asia/Ho_Chi_Minh). Timestamps are stored
// in UTC; the Vercel server also runs in UTC, so EVERY display format and
// "today" boundary must pin the zone explicitly or it drifts 7 hours. All of
// that lives here so no caller re-derives it inconsistently.

export const VN_TZ = "Asia/Ho_Chi_Minh";
const VN_OFFSET = "+07:00";

/** Mốc hiện tại (ms). Gói NGOÀI component để né rule react-hooks/purity khi so
 *  sánh "đã qua giờ chưa" trong event handler (Date.now là impure). */
export function nowMs(): number {
  return Date.now();
}

type TimeInput = string | Date | null | undefined;

function toDate(ts: TimeInput): Date | null {
  if (ts == null) return null;
  const d = typeof ts === "string" ? new Date(ts) : ts;
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "dd/MM/yyyy HH:mm" in Vietnam time. */
export function fmtDateTime(ts: TimeInput): string {
  const d = toDate(ts);
  return d
    ? d.toLocaleString("vi-VN", {
        timeZone: VN_TZ,
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "—";
}

/** True nếu mốc rơi đúng 00:00 giờ VN — dấu hiệu lịch CHỈ CÓ NGÀY (nguồn không
 *  nhập giờ). Phòng khám không đặt lịch lúc nửa đêm nên coi 00:00 = "chưa có giờ". */
export function isVnMidnight(ts: TimeInput): boolean {
  const d = toDate(ts);
  if (!d) return false;
  return (
    d.toLocaleTimeString("en-GB", {
      timeZone: VN_TZ,
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }) === "00:00"
  );
}

/** Giờ VN, hoặc "Chưa có giờ" nếu lịch chỉ có ngày (00:00). */
export function fmtTimeOrNone(ts: TimeInput): string {
  return isVnMidnight(ts) ? "Chưa có giờ" : fmtTime(ts);
}

/** "dd/MM/yyyy HH:mm", hoặc chỉ "dd/MM/yyyy" nếu lịch chỉ có ngày (00:00). */
export function fmtDateTimeOrDate(ts: TimeInput): string {
  return isVnMidnight(ts) ? fmtDate(ts) : fmtDateTime(ts);
}

/** "HH:mm" in Vietnam time (24h format). */
export function fmtTime(ts: TimeInput): string {
  const d = toDate(ts);
  return d
    ? d.toLocaleTimeString("vi-VN", {
        timeZone: VN_TZ,
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "—";
}

/** "dd/MM HH:mm" in Vietnam time (compact, e.g. the declined toast). */
export function fmtDayTime(ts: TimeInput): string {
  const d = toDate(ts);
  return d
    ? d.toLocaleString("vi-VN", {
        timeZone: VN_TZ,
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "—";
}

/** "dd/MM/yyyy" (date only) in Vietnam time. */
export function fmtDate(ts: TimeInput): string {
  const d = toDate(ts);
  return d
    ? d.toLocaleDateString("vi-VN", {
        timeZone: VN_TZ,
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      })
    : "—";
}

/** Hôm nay theo giờ Việt Nam, trả về `Date` ở nửa đêm giờ máy.
 *
 *  KHÔNG dùng `new Date()` trực tiếp khi cần "hôm nay": container chạy giờ UTC
 *  còn trình duyệt ở +07, nên từ 00:00 tới 07:00 giờ VN hai bên ra hai ngày
 *  khác nhau. Hàm này hỏi thẳng lịch VN nên chỗ nào gọi cũng ra cùng một ngày. */
export function vnToday(now: Date = new Date()): Date {
  const [y, m, d] = now
    .toLocaleDateString("en-CA", { timeZone: VN_TZ })
    .split("-")
    .map(Number);
  return new Date(y, m - 1, d);
}

/** "Ngày D tháng M năm YYYY" in Vietnam time. */
export function fmtVietnameseFullDate(ts: TimeInput): string {
  const d = toDate(ts);
  if (!d) return "—";
  const ymd = d.toLocaleDateString("en-CA", { timeZone: VN_TZ });
  const [y, m, dayNum] = ymd.split("-").map(Number);
  return `Ngày ${dayNum} tháng ${m} năm ${y}`;
}

/** "HH:mm" (mốc bắt đầu khung) + độ dài khung → "HH:mm-HH:mm", ví dụ
 *  ("17:00", 15) → "17:00-17:15". Dùng cho nhãn cột & tooltip lưới đặt chỗ.
 *
 *  C.3: `minutes` KHÔNG có mặc định 15. Độ dài khung là cấu hình của từng
 *  phòng khám (clinic.settings.booking.slot_minutes), nên một mặc định ở đây
 *  chỉ có tác dụng duy nhất là để một chỗ gọi thiếu tham số dán nhãn sai giờ
 *  lên đúng cái ô mà server sẽ từ chối. Thiếu thì báo lỗi biên dịch. */
export function slotRange(hhmm: string, minutes: number): string {
  const [h, m] = hhmm.split(":").map(Number);
  if (Number.isNaN(h) || Number.isNaN(m)) return hhmm;
  const end = h * 60 + m + minutes;
  const eh = Math.floor(end / 60) % 24;
  const em = end % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(h)}:${pad(m)} - ${pad(eh)}:${pad(em)}`;
}

/** A naive date ("YYYY-MM-DD") + time ("HH:mm") a Vietnam user typed → the
 *  correct UTC instant, regardless of the browser's own time zone. */
export function vnLocalToUtcISO(date: string, time: string): string {
  return new Date(`${date}T${time}:00${VN_OFFSET}`).toISOString();
}

/** [start, end) of "today" in Vietnam time, as UTC ISO strings — for day-window
 *  queries that must not drift on a UTC server. */
export function vnTodayRangeUtc(now: Date = new Date()): {
  startUtc: string;
  endUtc: string;
} {
  // en-CA renders a YYYY-MM-DD calendar date; pinning the zone gives Vietnam's.
  const ymd = now.toLocaleDateString("en-CA", { timeZone: VN_TZ });
  const start = new Date(`${ymd}T00:00:00${VN_OFFSET}`);
  const end = new Date(start.getTime() + 24 * 60 * 60 * 1000);
  return { startUtc: start.toISOString(), endUtc: end.toISOString() };
}

/** Start of the current month in Vietnam time, as a UTC ISO string. */
export function vnMonthStartUtc(now: Date = new Date()): string {
  const ymd = now.toLocaleDateString("en-CA", { timeZone: VN_TZ }); // YYYY-MM-DD
  const firstOfMonth = `${ymd.slice(0, 7)}-01`;
  return new Date(`${firstOfMonth}T00:00:00${VN_OFFSET}`).toISOString();
}
