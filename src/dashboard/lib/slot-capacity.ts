// Luật chỗ mỗi khung 15 phút (đặt lịch "rạp chiếu phim", 2026-07-02):
// mỗi BÁC SĨ × KHUNG 15' có đúng 3 chỗ — BN1 + BN2 cho lịch hẹn kênh thường
// (CSKH/Lễ tân đặt trước), chỗ thứ 3 DÀNH RIÊNG khách vãng lai (booking_channel
// = WALK_IN). Hàng "Chưa phân bác sĩ" (doctor_id null) cũng bị giới hạn y hệt
// như một hàng riêng. File THUẦN (không I/O) — dùng chung cho cả UI (sơ đồ chỗ)
// và server (POST/PATCH /api/appointments) để hai bên không lệch luật.

/** Độ dài 1 khung (phút). */
export const SLOT_MIN = 15;
/** Số chỗ kênh thường (BN1, BN2) mỗi bác sĩ mỗi khung. */
export const REGULAR_CAP = 2;
/** Số chỗ vãng lai (chỗ thứ 3) mỗi bác sĩ mỗi khung. */
export const WALKIN_CAP = 1;

/** Trạng thái KHÔNG còn giữ chỗ (huỷ / không đến / bác sĩ từ chối chờ phân lại). */
export const DEAD_STATUSES = ["CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"] as const;

export function isDeadStatus(status?: string | null): boolean {
  return (DEAD_STATUSES as readonly string[]).includes((status ?? "").trim());
}

export function isWalkinChannel(channel?: string | null): boolean {
  return (channel ?? "").trim().toUpperCase() === "WALK_IN";
}

const SLOT_MS = SLOT_MIN * 60_000;

/** Mốc đầu khung 15' chứa thời điểm iso (epoch ms). 15' chia hết 60' nên floor
 *  theo epoch UTC trùng khớp ranh giới khung giờ VN (lệch múi giờ là bội số giờ). */
export function slotBucketMs(iso: string): number {
  return Math.floor(Date.parse(iso) / SLOT_MS) * SLOT_MS;
}

/** ISO UTC của [đầu khung, cuối khung) chứa iso — dùng cho query range server. */
export function slotBucketRange(iso: string): { startUtc: string; endUtc: string } {
  const s = slotBucketMs(iso);
  return {
    startUtc: new Date(s).toISOString(),
    endUtc: new Date(s + SLOT_MS).toISOString(),
  };
}

export interface SlotApptLite {
  slot_start: string;
  doctor_id: string | null;
  booking_channel?: string | null;
  status?: string | null;
}

export interface SlotUsage {
  /** Số lịch kênh thường (chiếm BN1/BN2). */
  regular: number;
  /** Số lịch vãng lai (chiếm chỗ thứ 3). */
  walkin: number;
}

/** Key gộp: bác sĩ (null → "") + đầu khung. */
export function usageKey(doctorId: string | null | undefined, bucketMs: number): string {
  return `${doctorId ?? ""}|${bucketMs}`;
}

/** Gom danh sách lịch (đã bỏ/giữ nguyên trạng thái từ API) thành bảng chiếm chỗ
 *  theo (bác sĩ, khung 15'). Tự bỏ các trạng thái chết — API GET hiện đã lọc
 *  CANCELLED/NO_SHOW nhưng còn trả DOCTOR_DECLINED, nên vẫn phải lọc lại ở đây. */
export function buildSlotUsage(appts: SlotApptLite[]): Map<string, SlotUsage> {
  const m = new Map<string, SlotUsage>();
  for (const a of appts) {
    if (!a.slot_start || isDeadStatus(a.status)) continue;
    const t = Date.parse(a.slot_start);
    if (!Number.isFinite(t)) continue;
    const key = usageKey(a.doctor_id, Math.floor(t / SLOT_MS) * SLOT_MS);
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
