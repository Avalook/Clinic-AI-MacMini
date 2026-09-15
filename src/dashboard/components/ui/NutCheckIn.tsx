"use client";

/**
 * Nút check-in dùng chung cho mọi màn check-in (Trang chủ, lưới tuần, hàng chờ
 * Lễ tân, bảng lượt khám).
 *
 * BẤM LÀ CHECK-IN (Tuyền chốt lại 15/09/2026 tối). Bản sáng cùng ngày hỏi "đã
 * xác minh khách bằng cách nào" trước khi gửi; Tuyền bỏ: lễ tân tự xác nhận
 * bằng số điện thoại và nhìn mặt, ai check-in lúc nào đã có log.
 */

import type { ReactNode } from "react";

import Button, { type ButtonSize } from "./Button";

export default function NutCheckIn({
  onChon,
  disabled = false,
  size = "md",
  children = "Check-in",
  fullWidth = false,
}: {
  onChon: () => unknown;
  disabled?: boolean;
  size?: ButtonSize;
  children?: ReactNode;
  fullWidth?: boolean;
}) {
  return (
    <Button
      variant="primary"
      size={size}
      disabled={disabled}
      onClick={() => void onChon()}
      className={fullWidth ? "w-full" : undefined}
    >
      {children}
    </Button>
  );
}
