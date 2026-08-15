/**
 * Nút — MỘT chỗ duy nhất định nghĩa nút trông thế nào (DESIGN.md §5).
 *
 * Trước 15/08/2026 repo có 304 cái `<button>` tự vẽ bằng chuỗi class chép tay,
 * và không có component Button nào. Hệ quả người dùng nhìn thấy được: "các nút
 * mang hơi hướng thuần vẽ, góc bo mỏng hơn cạnh" (Tuyền, 15/08). Cái "góc mỏng"
 * là hiện tượng thật — viền `border` 1px chạy theo cung tròn bị khử răng cưa
 * nên đoạn cong nhạt hơn đoạn thẳng.
 *
 * Component này chữa tận gốc bằng cấu trúc, không bằng chỉnh từng nút:
 *
 *   · primary   phủ màu đặc, KHÔNG viền — không có viền thì không có góc mỏng
 *   · secondary "viền" là `ring-inset` (box-shadow) — ring vẽ đè lên nền nên
 *               không bị antialiasing ăn mòn ở góc như border
 *   · ghost     không nền không viền, hover mới hiện nền
 *   · danger    trắng + ring đỏ nhạt — dành cho hành động phá huỷ
 *
 * Cỡ theo thang: sm 28px (trong bảng) · md 32px (mặc định) · lg 40px (điện
 * thoại / hành động chính — 40px là cỡ ngón tay chạm tin cậy được).
 *
 * Màn nào cần nút là import từ đây. Tự vẽ một cái `<button className="...">`
 * mới là quay lại đúng cái bệnh 304 bản sao.
 */

import { forwardRef, type ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

const VARIANT: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-600 text-white hover:bg-brand-700 active:bg-brand-800 " +
    "disabled:bg-brand-200",
  secondary:
    "bg-surface text-ink ring-1 ring-inset ring-line-strong " +
    "hover:bg-surface-muted active:bg-surface-sunken disabled:text-ink-faint",
  ghost:
    "bg-transparent text-ink-muted hover:bg-surface-sunken hover:text-ink " +
    "disabled:text-ink-faint",
  danger:
    "bg-surface text-danger ring-1 ring-inset ring-danger/30 " +
    "hover:bg-danger-bg/40 disabled:text-ink-faint disabled:ring-line",
};

const SIZE: Record<ButtonSize, string> = {
  sm: "h-7 px-3 text-meta",
  md: "h-8 px-3.5 text-body",
  lg: "h-10 px-4 text-emph",
};

/** Vỏ nút cho phần tử KHÔNG phải <button> — chủ yếu là <Link> điều hướng
 *  trông như nút. Link và button là hai việc khác nhau (điều hướng vs hành
 *  động) nên phần tử phải đúng; chỉ cái vỏ là dùng chung. */
export function buttonClass(
  variant: ButtonVariant = "secondary",
  size: ButtonSize = "md",
): string {
  return (
    "inline-flex items-center justify-center gap-1.5 whitespace-nowrap " +
    "rounded-control font-medium transition-colors duration-100 " +
    "focus-visible:outline-2 focus-visible:outline-offset-2 " +
    "focus-visible:outline-brand-500 disabled:cursor-not-allowed " +
    `${VARIANT[variant]} ${SIZE[size]}`
  );
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", className = "", type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      // `type="button"` mặc định: một nút trần trong <form> là nút submit, và
      // đã có màn lưu hồ sơ vì một nút "Huỷ" quên khai type.
      type={type}
      className={`${buttonClass(variant, size)} ${className}`}
      {...rest}
    />
  );
});

export default Button;
