// Shared form design tokens + option lists, so the intake form and the
// appointment-booking form look identical and stay consistent. Aesthetic
// matches the dashboard (rose accent, hairline borders, 8-12px radius,
// soft shadow). text-base on mobile prevents iOS auto-zoom; denser at ≥sm.

export const INPUT =
  "w-full min-h-11 rounded-lg border border-line bg-white px-3 py-2.5 " +
  "text-base text-ink shadow-[0_1px_2px_rgba(0,0,0,0.03)] outline-none " +
  "transition-colors placeholder:text-ink-faint focus:border-brand-600 " +
  "focus:ring-2 focus:ring-brand-600/15 sm:min-h-0 sm:py-2 sm:text-sm";

export const LABEL = "mb-1 block text-[13px] font-medium text-ink-soft";

export const BTN =
  "min-h-11 w-full rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold " +
  "text-white shadow-[0_1px_2px_rgba(236,72,153,0.3)] transition-colors " +
  "hover:bg-brand-700 active:bg-brand-700 disabled:opacity-50 sm:w-auto";

export const BTN_GHOST =
  "min-h-11 w-full rounded-lg border border-line bg-white px-5 py-2.5 " +
  "text-sm font-medium text-ink-soft transition-colors hover:bg-surface-sunken " +
  "active:bg-surface-sunken sm:w-auto";

export const CARD =
  "rounded-xl border border-line bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.06)] sm:p-6";

// ===== Bảng — tông hồng nhẹ dùng CHUNG cho mọi bảng trong dashboard =====
// (khớp gradient thẻ thông tin BN: nền hồng #fdf2f8, viền #f9d9e8, header #fce7f3).
// TBL_WRAP: khung ngoài bảng · TBL_HEAD: hàng tiêu đề · TBL_ROW: hàng cuộn (zebra hồng)
// · TBL_DIV: đường kẻ ngang giữa các hàng.
export const TBL_WRAP =
  "overflow-hidden rounded-xl border border-brand-100 bg-white shadow-[0_1px_3px_rgba(236,72,153,0.08)]";
export const TBL_HEAD =
  "bg-brand-100 text-[11px] font-semibold uppercase tracking-wide text-brand-800";
export const TBL_ROW = "transition-colors hover:bg-brand-50";
export const TBL_ROW_ALT = "bg-white even:bg-[#fdf5f9]";
export const TBL_DIV = "divide-y divide-brand-100";

// Khung bảng cuộn ngang+dọc: dùng overflow-auto + max-h để giới hạn chiều cao.
// Bắt buộc đặt thead className sticky top-0 z-10 để header cố định khi cuộn.

// Booking option lists (single source of truth).
export const CHANNELS = [
  { id: "WALK_IN", label: "Khách tới trực tiếp" },
  { id: "HOTLINE", label: "Hotline" },
  { id: "ZALO_PK", label: "Zalo" },
  { id: "FB_DR4WOMEN", label: "Facebook" },
  { id: "REFERRAL", label: "Giới thiệu" },
];

export const DURATIONS = [15, 30, 45, 60];
