// Capacity Phase 1 — ngân sách tải bác sĩ Thành theo khung-giờ + trần ca mới (newCap).
// Task T-20260629-CAP-01 (Decision Doc v2). Pure helpers, KHÔNG I/O — route.ts lo query,
// gọi các hàm này. Tách khỏi lib/queue.ts (queue.ts chỉ lo callRank thứ tự gọi).
// TODO[D017]: Phase sau dời logic này vào LangGraph Scheduling sub-graph.
// TODO[Phase1.5]: thêm RPC + pg_advisory_xact_lock để chống race (hiện best-effort, DEC-7).

import { VN_TZ } from "./datetime";

export type PatientKind = "NEW" | "RETURN";

// V2#9 — tải mặc định bảo thủ cho appointment cũ chưa có thanh_min (NULL) để không bị tính = 0.
export const FALLBACK_THANH_MIN = 12;

// Đề xuất tải theo loại khách (DEC-3: chỉ GỢI Ý, CSKH sửa được). K1: hard-code map vì
// service_type.default_duration_minutes không tách B1+B3 vs siêu âm, không phân mới/tái.
export function suggestLoad(
  kind: PatientKind,
  needSono: boolean,
): { thanh_min: number; sono_min: number } {
  if (kind === "NEW") return { thanh_min: 15, sono_min: needSono ? 12 : 0 };
  return { thanh_min: needSono ? 7 : 5, sono_min: needSono ? 8 : 0 };
}

// Khung-giờ VN của một slot (ISO UTC). Dùng Asia/Ho_Chi_Minh — KHÔNG getUTCHours() (V2#2).
// weekday: 0=CN .. 6=T7 (khớp block_budget.weekday).
export function vnBlockOf(slotStartIso: string): { weekday: number; hour_start: number } {
  const d = new Date(slotStartIso);
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: VN_TZ,
    hour: "2-digit",
    hour12: false,
    weekday: "short",
  }).formatToParts(d);
  const hourStr = parts.find((p) => p.type === "hour")?.value ?? "0";
  const wdStr = parts.find((p) => p.type === "weekday")?.value ?? "Sun";
  const WD: Record<string, number> = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
  // "24" có thể xuất hiện ở một số runtime cho nửa đêm → quy về 0.
  const hour = Number(hourStr) % 24;
  return { weekday: WD[wdStr] ?? 0, hour_start: hour };
}

export interface BudgetRow {
  location_id: string;
  doctor_id: string | null;
  weekday: number | null;
  hour_start: number;
  thanh_budget_min: number;
  sono_budget_min: number;
  online_quota_min: number;
  walkin_quota_min: number;
  buffer_min: number;
  new_cap: number;
  max_total: number;
}

// Một appointment đã tồn tại trong khung (chỉ các trường cần để tính tải).
export interface ApptLite {
  patient_kind: PatientKind | null;
  thanh_min: number | null;
  booking_channel: string | null;
}

export function isWalkin(channel: string | null): boolean {
  return (channel ?? "").toUpperCase() === "WALK_IN";
}

// Tải Thành của 1 ca: thanh_min, COALESCE NULL → FALLBACK (V2#9).
export function loadOfAppt(a: ApptLite): number {
  return a.thanh_min ?? FALLBACK_THANH_MIN;
}

// new_cap chỉ đếm ca có patient_kind === 'NEW' tường minh; ca cũ (NULL) KHÔNG tính vào
// trần ca-mới (tránh legacy chặn oan), nhưng vẫn tính tải Thành qua loadOfAppt.
export function isNewExplicit(a: ApptLite): boolean {
  return a.patient_kind === "NEW";
}

export interface Usage {
  thanh: number;
  online: number;
  walkin: number;
  new_count: number;
  total: number;
}

// Tổng hợp tải hiện có của một khung (cho quote endpoint vẽ ô lịch).
export function usageOf(existing: ApptLite[]): Usage {
  let thanh = 0;
  let online = 0;
  let walkin = 0;
  let newCount = 0;
  for (const a of existing) {
    const load = loadOfAppt(a);
    thanh += load;
    if (isWalkin(a.booking_channel)) walkin += load;
    else online += load;
    if (isNewExplicit(a)) newCount += 1;
  }
  return { thanh, online, walkin, new_count: newCount, total: existing.length };
}

// Trạng thái ô lịch để hiển thị (không phải quyết định chặn — đó là evaluateBudget).
export type CellState =
  | "free" // Trống
  | "few" // Còn ít
  | "return_only" // Chỉ tái khám (hết new_cap)
  | "full_thanh" // Đầy-Thành
  | "walkin_hold" // Giữ vãng lai
  | "locked"; // Khoá (đầy tổng)

export function cellState(budget: BudgetRow, u: Usage): CellState {
  if (u.total >= budget.max_total) return "locked";
  if (u.thanh >= budget.thanh_budget_min) return "full_thanh";
  if (u.new_count >= budget.new_cap) return "return_only";
  // còn slot nhưng online gần cạn, dành phần cho vãng lai
  if (u.online >= budget.online_quota_min && u.walkin < budget.walkin_quota_min)
    return "walkin_hold";
  if (u.thanh >= budget.thanh_budget_min - 10) return "few";
  return "free";
}

// DEC-8 — chọn dòng ngân sách theo độ-cụ-thể giảm dần; null ⇒ caller fail-open.
export function resolveBudget(
  rows: BudgetRow[],
  key: { location_id: string; doctor_id: string | null; weekday: number; hour_start: number },
): BudgetRow | null {
  const atLoc = rows.filter(
    (r) => r.location_id === key.location_id && r.hour_start === key.hour_start,
  );
  const pick = (docMatch: boolean, wdMatch: boolean) =>
    atLoc.find((r) =>
      (docMatch ? r.doctor_id === key.doctor_id : r.doctor_id === null) &&
      (wdMatch ? r.weekday === key.weekday : r.weekday === null),
    ) ?? null;
  if (key.doctor_id) {
    return (
      pick(true, true) ?? pick(true, false) ?? pick(false, true) ?? pick(false, false)
    );
  }
  return pick(false, true) ?? pick(false, false);
}

export type BudgetStatus =
  | "available"
  | "warning"
  | "warning_buffer"
  | "full_total"
  | "full_new"
  | "full_online"
  | "full_thanh";

export interface BudgetUsed {
  thanh: number;
  online: number;
  walkin: number;
  new_count: number;
  total: number;
  thanh_budget: number;
  new_cap: number;
  online_quota: number;
}

export interface Candidate {
  patient_kind: PatientKind;
  thanh_min: number;
  booking_channel: string | null;
}

// Cốt lõi canBook — thuần, không I/O. Thứ tự kiểm theo §5 packet.
export function evaluateBudget(
  budget: BudgetRow,
  existing: ApptLite[],
  cand: Candidate,
): { status: BudgetStatus; reason: string; used: BudgetUsed } {
  let thanh = 0;
  let online = 0;
  let walkin = 0;
  let newCount = 0;
  for (const a of existing) {
    const load = loadOfAppt(a);
    thanh += load;
    if (isWalkin(a.booking_channel)) walkin += load;
    else online += load;
    if (isNewExplicit(a)) newCount += 1;
  }
  const total = existing.length;
  const candWalkin = isWalkin(cand.booking_channel);
  const used: BudgetUsed = {
    thanh,
    online,
    walkin,
    new_count: newCount,
    total,
    thanh_budget: budget.thanh_budget_min,
    new_cap: budget.new_cap,
    online_quota: budget.online_quota_min,
  };

  // 1) max_total (V2#6 — giữ "≤12 ca/giờ")
  if (total + 1 > budget.max_total) {
    return { status: "full_total", reason: "Khung đã đủ số ca tối đa.", used };
  }
  // 2) new_cap — trần ca mới
  if (cand.patient_kind === "NEW" && newCount + 1 > budget.new_cap) {
    return { status: "full_new", reason: "Khung đã đủ trần ca khám mới.", used };
  }
  // 3) quota theo kênh (V2#5)
  if (candWalkin) {
    if (walkin + cand.thanh_min > budget.walkin_quota_min) {
      // còn buffer thì cho nhận nhưng cảnh báo
      if (thanh + cand.thanh_min <= budget.thanh_budget_min + budget.buffer_min) {
        return { status: "warning_buffer", reason: "Vượt quota vãng lai — đang dùng buffer.", used };
      }
      return { status: "full_thanh", reason: "Hết quota vãng lai và buffer.", used };
    }
  } else if (online + cand.thanh_min > budget.online_quota_min) {
    return { status: "full_online", reason: "Khung đã đầy quota đặt trước (online).", used };
  }
  // 4) tổng ngân sách Thành
  if (thanh + cand.thanh_min > budget.thanh_budget_min) {
    return { status: "full_thanh", reason: "Khung đã đầy tải bác sĩ Thành.", used };
  }
  // 5) sát ngưỡng → cảnh báo mềm (còn < 1 ca tái khám ngắn)
  if (thanh + cand.thanh_min > budget.thanh_budget_min - 5) {
    return { status: "warning", reason: "Khung gần đầy — chỉ nên nhận thêm ca ngắn.", used };
  }
  return { status: "available", reason: "Còn nhận.", used };
}

export const BLOCKING_STATUSES: BudgetStatus[] = [
  "full_total",
  "full_new",
  "full_online",
  "full_thanh",
];

export function isBlocking(s: BudgetStatus): boolean {
  return BLOCKING_STATUSES.includes(s);
}
