import { forwardRef, type InputHTMLAttributes } from "react";

/** Ô nhập chuẩn: màn nghiệp vụ chỉ truyền độ rộng, không tự vẽ input. */
const ONhap = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function ONhap({ className = "", ...props }, ref) {
    return (
      <input
        ref={ref}
        className={`min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink ${className}`}
        {...props}
      />
    );
  },
);

export default ONhap;
