/**
 * Màu cố định theo MÃ người (bác sĩ…) — thanh "Tải bác sĩ" ở Trang chủ
 * (27/09/2026). Lấy từ bộ nền/chữ của Chip (token sẵn có), chọn bằng băm ổn
 * định: cùng một bác sĩ luôn cùng một màu ở mọi lần tải.
 */

const BO_MAU = [
  "bg-brand-50 text-brand-700",
  "bg-status-assigned-bg text-status-assigned",
  "bg-warning-bg text-warning",
  "bg-status-in-progress-bg text-status-in-progress",
  "bg-status-dang-o-bg text-status-dang-o",
  "bg-success-bg text-success",
] as const;

/** Lớp nền nhạt + chữ đậm cùng họ. Rỗng (chưa xếp bác sĩ) → xám. */
export function mauTheoMa(ma: string | null | undefined): string {
  if (!ma) return "bg-surface-sunken text-ink-muted";
  let h = 0;
  for (let i = 0; i < ma.length; i++) h = (h * 31 + ma.charCodeAt(i)) >>> 0;
  return BO_MAU[h % BO_MAU.length];
}
