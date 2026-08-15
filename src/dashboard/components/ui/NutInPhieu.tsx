/**
 * Nút "In phiếu" — MỘT mặt cho cùng một việc, ở mọi màn.
 *
 * Trước 15/08/2026 repo có 7 chỗ tự vẽ link in phiếu với 3 kiểu khác nhau
 * (viền success-bg ở hàng đợi Lễ tân, viền success đặc ở panel bác sĩ, viền
 * xám ở màn siêu âm) — cùng một hành động mà ba bộ mặt, và cả ba đều dùng
 * `border` 1px trên góc bo, tức đúng cái lỗi "góc mỏng hơn cạnh" DESIGN.md §5
 * đã chẩn. Ở đây "viền" là ring-inset như Button, và tông success cố định —
 * in phiếu là hành động kết thúc tốt đẹp của một lượt khám.
 *
 * Là <a target="_blank"> chứ không phải <button>: mở trang in ở tab mới là
 * ĐIỀU HƯỚNG. Cỡ theo đúng thang của Button: sm trong bảng, md trong danh
 * sách, lg cho hành động chính của panel.
 */

import type { ReactNode } from "react";
import { Printer } from "lucide-react";
import type { ButtonSize } from "./Button";

const SIZE: Record<ButtonSize, string> = {
  sm: "h-7 px-2.5 text-label",
  md: "h-8 px-3 text-meta",
  lg: "h-10 px-4 text-emph",
};

const ICON: Record<ButtonSize, number> = { sm: 12, md: 13, lg: 16 };

export default function NutInPhieu({
  href,
  size = "sm",
  fullWidth = false,
  children = "In phiếu",
}: {
  href: string;
  size?: ButtonSize;
  /** Panel hồ sơ bác sĩ: nút chiếm trọn bề ngang cột. */
  fullWidth?: boolean;
  children?: ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={
        "inline-flex shrink-0 items-center justify-center gap-1.5 " +
        "whitespace-nowrap rounded-control bg-surface font-semibold " +
        "text-success ring-1 ring-inset ring-success-bg transition-colors " +
        "duration-100 hover:bg-success-bg " +
        `${SIZE[size]}${fullWidth ? " w-full" : ""}`
      }
    >
      <Printer size={ICON[size]} /> {children}
    </a>
  );
}
