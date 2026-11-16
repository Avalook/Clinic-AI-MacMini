// TIN BẢNG ĐỔI, KÈM ID LƯỢT — thứ đi qua `SU_KIEN_BANG` trên window (16/11/2026).
//
// Máy chủ gửi `{t: bảng, c: phòng khám, v?: id lượt}` (trigger `notify_row_change`,
// migration 20261116200000). `v` chỉ có khi hàng có cột `visit_id`.
//
// VÌ SAO. Trước đây tin chỉ có tên bảng, nên phiếu đang mở của khách B hỏi lại mỗi
// khi lượt của khách A đổi. Đo prod 13–16/11: một lượt ghi kéo theo ~15 GET trong
// 1,5 giây, đỉnh 443 lượt/phút/người, 1.834 lượt 429. Người nghe theo MỘT lượt
// (`useNgheBang(…, { luot })`) nay bỏ được tin của lượt khác.
//
// BẤT BIẾN: KHÔNG BAO GIỜ BỎ SÓT. Tin "không rõ" (`t: null` — tab vừa hiện lại,
// dòng vừa nối lại, hàng đợi máy chủ bị đầy, tin méo) và tin không có `v` đều làm
// người nghe hỏi lại như trước. Lọc theo lượt chỉ BỚT việc thừa, không bao giờ
// thêm một chỗ mù.

export interface TinBang {
  /** Bảng vừa đổi; `null` = không rõ bảng nào → mọi người nghe hỏi lại. */
  t: string | null;
  /** Id lượt của hàng vừa đổi; `null` = bảng không có cột lượt (hoặc không rõ). */
  v?: string | null;
}

export const TIN_KHONG_RO: TinBang = { t: null, v: null };

/** Đọc `data` của sự kiện SSE `change`. Méo → không rõ: thà thừa một lượt tải. */
export function docTin(data: string): TinBang {
  try {
    const d = JSON.parse(data) as { t?: unknown; v?: unknown };
    if (typeof d.t !== "string" || !d.t) return TIN_KHONG_RO;
    return { t: d.t, v: typeof d.v === "string" && d.v ? d.v : null };
  } catch {
    return TIN_KHONG_RO;
  }
}

/**
 * Người nghe các bảng `bang` — đang mở lượt `luot` nếu có — có phải hỏi lại không.
 * Không truyền `luot` thì y như hành vi cũ: chỉ lọc theo bảng.
 */
export function canHoiLai(
  tin: TinBang | null | undefined,
  bang: ReadonlySet<string>,
  luot?: string | null,
): boolean {
  if (!tin || tin.t === null) return true;
  if (!bang.has(tin.t)) return false;
  if (!luot || !tin.v) return true;
  return tin.v === luot;
}
