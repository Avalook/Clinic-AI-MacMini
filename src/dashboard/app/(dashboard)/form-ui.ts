// Shared form design tokens + option lists, so the intake form and the
// appointment-booking form look identical and stay consistent. Aesthetic
// matches the dashboard (rose accent, hairline borders, 8-12px radius,
// soft shadow). text-base on mobile prevents iOS auto-zoom; denser at ≥sm.

export const INPUT =
  "w-full min-h-11 rounded-lg border border-[#e4e4e7] bg-white px-3 py-2.5 " +
  "text-base text-[#171717] shadow-[0_1px_2px_rgba(0,0,0,0.03)] outline-none " +
  "transition-colors placeholder:text-[#a1a1aa] focus:border-[#ec4899] " +
  "focus:ring-2 focus:ring-[#ec4899]/15 sm:min-h-0 sm:py-2 sm:text-sm";

export const LABEL = "mb-1 block text-[13px] font-medium text-[#3f3f46]";

export const BTN =
  "min-h-11 w-full rounded-lg bg-[#ec4899] px-5 py-2.5 text-sm font-semibold " +
  "text-white shadow-[0_1px_2px_rgba(236,72,153,0.3)] transition-colors " +
  "hover:bg-[#db2777] active:bg-[#db2777] disabled:opacity-50 sm:w-auto";

export const BTN_GHOST =
  "min-h-11 w-full rounded-lg border border-[#e4e4e7] bg-white px-5 py-2.5 " +
  "text-sm font-medium text-[#52525b] transition-colors hover:bg-[#f4f4f5] " +
  "active:bg-[#f4f4f5] sm:w-auto";

export const CARD =
  "rounded-xl border border-[#e4e4e7] bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.06)] sm:p-6";

// ===== Bảng — tông hồng nhẹ dùng CHUNG cho mọi bảng trong dashboard =====
// (khớp gradient thẻ thông tin BN: nền hồng #fdf2f8, viền #f9d9e8, header #fce7f3).
// TBL_WRAP: khung ngoài bảng · TBL_HEAD: hàng tiêu đề · TBL_ROW: hàng cuộn (zebra hồng)
// · TBL_DIV: đường kẻ ngang giữa các hàng.
export const TBL_WRAP =
  "overflow-hidden rounded-xl border border-[#f3cfe0] bg-white shadow-[0_1px_3px_rgba(236,72,153,0.08)]";
export const TBL_HEAD =
  "bg-[#fce7f3] text-[11px] font-semibold uppercase tracking-wide text-[#9d2463]";
export const TBL_ROW = "transition-colors hover:bg-[#fdf2f8]";
export const TBL_ROW_ALT = "bg-white even:bg-[#fdf5f9]";
export const TBL_DIV = "divide-y divide-[#f6e0ec]";

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
