/**
 * One cell of the KPI row that opens almost every screen in the design set
 * ("Cần xử lý hôm nay 12 · Quá SLA 3 · Chờ xác nhận 8 · Đã hoàn thành 24").
 *
 * The row is a filter, not decoration: in the designs the numbers correspond to
 * the tabs below them, so a cell is clickable when it narrows the list. A cell
 * with no `href` renders as plain text rather than a dead button, because a
 * control that looks pressable and is not is worse than one that never invited
 * the press.
 */

import Link from "next/link";
import type { ReactNode } from "react";

export type StatTone = "neutral" | "brand" | "warning" | "danger" | "success";

const TONE: Record<StatTone, { icon: string; value: string }> = {
  neutral: { icon: "text-ink-muted bg-surface-sunken", value: "text-ink" },
  brand: { icon: "text-brand-600 bg-brand-50", value: "text-ink" },
  warning: { icon: "text-warning bg-warning-bg", value: "text-warning" },
  danger: { icon: "text-status-overdue bg-status-overdue-bg", value: "text-status-overdue" },
  success: { icon: "text-status-completed bg-status-completed-bg", value: "text-status-completed" },
};

export interface StatCardProps {
  label: string;
  value: number | string;
  icon?: ReactNode;
  tone?: StatTone;
  /** When set, the cell filters the list below it. */
  href?: string;
  /**
   * Biến thể lọc TẠI CHỖ, cho màn hình giữ bộ lọc trong state thay vì trong
   * URL. Cùng vai trò với `href`, khác cách điều hướng.
   *
   * Có nó thì không cần một hàng tab riêng bên dưới lặp lại đúng những con số
   * này — hai chỗ bấm cho một việc là hai chỗ để lệch nhau.
   */
  onSelect?: () => void;
  /** Marks the cell whose filter is currently applied. */
  active?: boolean;
}

export default function StatCard({
  label,
  value,
  icon,
  tone = "neutral",
  href,
  onSelect,
  active = false,
}: StatCardProps) {
  const t = TONE[tone];
  const body = (
    <span className="flex items-center gap-3">
      {icon ? (
        <span
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full ${t.icon}`}
          aria-hidden
        >
          {icon}
        </span>
      ) : null}
      <span className="flex flex-col">
        <span className="text-sm text-ink-muted">{label}</span>
        <span className={`text-2xl leading-tight font-semibold ${t.value}`}>
          {value}
        </span>
      </span>
    </span>
  );

  // Ô ĐANG LỌC phải nhìn ra được ngay, không chỉ bằng nền xám nhạt: người dùng
  // nhìn con số trước, nền sau. Viền dày bên trái là thứ thấy được từ xa.
  const kieuChon = active
    ? "bg-surface-sunken ring-1 ring-inset ring-brand-500"
    : "";

  if (onSelect) {
    return (
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={active}
        className={`flex-1 rounded-card px-5 py-4 text-left transition-colors hover:bg-surface-sunken ${kieuChon}`}
      >
        {body}
      </button>
    );
  }

  if (!href) {
    return <div className="flex-1 px-5 py-4">{body}</div>;
  }

  return (
    <Link
      href={href}
      aria-current={active ? "true" : undefined}
      className={`flex-1 rounded-card px-5 py-4 transition-colors hover:bg-surface-sunken ${kieuChon}`}
    >
      {body}
    </Link>
  );
}

/** The row itself: cells separated by hairlines, on one card. */
export function StatRow({ children }: { children: ReactNode }) {
  return (
    <div className="flex divide-x divide-line rounded-card border border-line bg-surface shadow-card">
      {children}
    </div>
  );
}
