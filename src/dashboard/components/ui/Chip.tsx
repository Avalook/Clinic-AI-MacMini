/**
 * Chip ngữ nghĩa chung — cho nhãn KHÔNG thuộc bộ từ vựng trạng thái.
 *
 * Phân công giữa hai component chip (DESIGN.md §5):
 *
 *   · `StatusChip`  — TRẠNG THÁI của một thực thể (lịch hẹn, việc, lượt khám).
 *                     Tone của nó là bộ từ vựng đóng, map ở lib/*-status.ts.
 *   · `Chip` (đây)  — mọi nhãn còn lại: "Khám mới/cũ", "+2 việc", "Mới",
 *                     "tự chọn", đếm số… Trước 15/08 những nhãn này được vẽ
 *                     tay tại chỗ bằng chuỗi class — mỗi màn một cỡ, một bo
 *                     góc, một đệm khác nhau, và đó là một phần cảm giác
 *                     "sao sao" của giao diện.
 *
 * Cùng hình dạng với StatusChip (chữ nhật mềm rounded-chip 6px, nền nhạt +
 * chữ đậm cùng họ, KHÔNG viền) để hai loại chip đứng cạnh nhau không lệch.
 */

import type { ReactNode } from "react";

export type ChipTone = "success" | "warning" | "danger" | "brand" | "neutral";

const TONE: Record<ChipTone, string> = {
  success: "bg-success-bg text-success",
  warning: "bg-warning-bg text-warning",
  danger: "bg-danger-bg text-danger",
  brand: "bg-brand-50 text-brand-700",
  neutral: "bg-surface-sunken text-ink-muted",
};

/** Vỏ chip cho phần tử KHÔNG phải <span> — ví dụ một chip bấm được phải là
 *  <button> thật (span có onClick là mất bàn phím + trình đọc màn hình).
 *  Dùng hàm này thay vì chép chuỗi class: chép là hai bản sao chờ lệch nhau. */
export function chipClass(tone: ChipTone): string {
  return (
    "inline-flex h-5 items-center gap-1 whitespace-nowrap rounded-chip " +
    `px-2 text-label font-medium ${TONE[tone]}`
  );
}

export default function Chip({
  tone = "neutral",
  children,
  title,
  className = "",
}: {
  tone?: ChipTone;
  children: ReactNode;
  title?: string;
  className?: string;
}) {
  return (
    <span
      title={title}
      className={`${chipClass(tone)} ${className}`}
    >
      {children}
    </span>
  );
}
