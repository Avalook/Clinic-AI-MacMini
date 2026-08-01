// Shared form design tokens + option lists, so the intake form and the
// appointment-booking form look identical and stay consistent. Aesthetic
// matches the dashboard (teal accent, hairline borders, 8-12px radius,
// token shadow). text-base on mobile prevents iOS auto-zoom; denser at ≥sm.

export const INPUT =
  "w-full min-h-11 rounded-lg border border-line bg-surface px-3 py-2.5 " +
  "text-base text-ink shadow-card outline-none " +
  "transition-colors placeholder:text-ink-faint focus:border-brand-600 " +
  "focus:ring-2 focus:ring-brand-600/15 sm:min-h-0 sm:py-2 sm:text-sm";

export const LABEL = "mb-1 block text-[13px] font-medium text-ink-soft";

export const BTN =
  "min-h-11 w-full rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold " +
  "text-white shadow-card transition-colors " +
  "hover:bg-brand-700 active:bg-brand-700 disabled:opacity-50 sm:w-auto";

export const BTN_GHOST =
  "min-h-11 w-full rounded-lg border border-line bg-white px-5 py-2.5 " +
  "text-sm font-medium text-ink-soft transition-colors hover:bg-surface-sunken " +
  "active:bg-surface-sunken sm:w-auto";

export const CARD =
  "rounded-card border border-line bg-surface p-5 shadow-card sm:p-6";

// ===== Bảng — token bề mặt dùng CHUNG cho mọi bảng trong dashboard =====
// TBL_WRAP: khung ngoài bảng · TBL_HEAD: hàng tiêu đề · TBL_ROW: hàng cuộn (zebra nhẹ)
// · TBL_DIV: đường kẻ ngang giữa các hàng.
export const TBL_WRAP =
  "overflow-hidden rounded-card border border-line bg-surface shadow-card";
export const TBL_HEAD =
  "bg-surface-muted text-[11px] font-semibold uppercase tracking-wide text-ink-soft";
export const TBL_ROW = "transition-colors hover:bg-brand-50";
export const TBL_ROW_ALT = "bg-surface even:bg-surface-muted";
export const TBL_DIV = "divide-y divide-line";

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
