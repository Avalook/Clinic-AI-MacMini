"use client";

/**
 * Chip CHỌN — ô tick (nhiều lựa chọn) / ô radio (một lựa chọn) dạng chip, Y HỆT
 * bản giao diện mẫu (`.tk`, 27/09/2026): chữ nhật bo 8, viền bằng ring-inset
 * (không `border` — DESIGN.md §5), đang chọn thì nền `surface-selected` + chữ
 * brand. Ô input THẬT nằm trong chip: bàn phím, trình đọc màn hình, form đều
 * chạy như checkbox/radio thường.
 *
 * Radio bấm lại lựa chọn đang chọn → `onBoChon` (nếu có) để bỏ chọn — radio
 * thường không bỏ được, bác sĩ tick nhầm là kẹt.
 */

import type { ReactNode } from "react";

export default function ChipChon({
  kieu = "tick",
  ten,
  chon,
  onDoi,
  onBoChon,
  disabled,
  children,
}: {
  kieu?: "tick" | "mot";
  /** `name` của nhóm radio. */
  ten?: string;
  chon: boolean;
  onDoi: () => void;
  onBoChon?: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <label
      className={`inline-flex min-h-10 select-none items-center gap-1.5 rounded-control px-2.5 py-1 text-body ring-1 ring-inset transition-colors sm:min-h-8 ${
        chon
          ? "bg-surface-selected font-medium text-brand-700 ring-brand-100"
          : "bg-surface text-ink ring-line"
      } ${disabled ? "cursor-not-allowed opacity-70" : "cursor-pointer"}`}
    >
      <input
        type={kieu === "mot" ? "radio" : "checkbox"}
        name={ten}
        checked={chon}
        disabled={disabled}
        onChange={onDoi}
        onClick={kieu === "mot" && chon && onBoChon ? onBoChon : undefined}
        className="m-0 size-4 accent-brand-600"
      />
      {children}
    </label>
  );
}
