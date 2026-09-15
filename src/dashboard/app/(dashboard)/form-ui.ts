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

// NHÃN NẰM CÙNG DÒNG VỚI Ô NHẬP (Tuyền 16/09/2026: *"ô nhãn cùng dòng tiêu đề
// luôn, kiểu nó tiết kiệm được diện tích mà nhìn cũng dễ nhìn"*).
//
// Dùng cho ô ngắn, ít chữ (Quốc tịch, Nghề nghiệp, Đối tượng…). Ô có lỗi in
// dưới hoặc có ghi chú dài thì vẫn để nhãn trên — đọc theo chiều dọc dễ hơn.
//
// DƯỚI 640px NHÃN QUAY VỀ TRÊN: 375px mà kẹp nhãn 128px cạnh ô nhập thì ô nhập
// còn ~200px, và nhãn dài ("Địa chỉ chi tiết…") tự xuống ba dòng — tiết kiệm
// diện tích ở chỗ này là lấy mất chỗ ở chỗ khác. Đây là cùng một luật với thẻ
// ở DESIGN.md §7: nghiệm thu đủ 375/768/1280.
export const HANG = "flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3";
// Suy từ LABEL chứ không chép lại: cỡ chữ của nhãn chỉ được khai MỘT LẦN, nếu
// không thì hai kiểu nhãn trôi khỏi nhau (và bộ đếm kích thước tự chế đếm đúng
// cái chép lại ấy).
export const HANG_LABEL = LABEL.replace("mb-1 block", "sm:w-36 sm:shrink-0");
// Bản HẸP: nhãn chỉ rộng bằng chữ của nó. Dùng khi hàng còn thứ khác ngoài ô
// nhập (ô tích "Chỉ biết năm") — nhãn 144px cố định bóp ô ngày còn ~55px, đủ
// hẹp để "DD/MM/YYYY" bị cắt cụt.
export const HANG_LABEL_HEP = LABEL.replace("mb-1 block", "sm:shrink-0");

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
// Tuyền chốt 16/09/2026: Điện thoại · Hotline · Zalo · Facebook · Website ·
// Giới thiệu · Trực tiếp. Mã cũ giữ nguyên (lịch đã ghi dùng chúng).
export const CHANNELS = [
  { id: "WALK_IN", label: "Trực tiếp" },
  { id: "DIEN_THOAI", label: "Điện thoại" },
  { id: "HOTLINE", label: "Hotline" },
  { id: "ZALO_PK", label: "Zalo" },
  { id: "FB_DR4WOMEN", label: "Facebook" },
  { id: "WEBSITE", label: "Website" },
  { id: "REFERRAL", label: "Giới thiệu" },
];

export const DURATIONS = [15, 30, 45, 60];
