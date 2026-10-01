import { forwardRef, type SelectHTMLAttributes } from "react";

/** Danh sách chọn chuẩn: màn nghiệp vụ chỉ cung cấp option và độ rộng. */
const OChon = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function OChon({ className = "", ...props }, ref) {
    return (
      <select
        ref={ref}
        className={`min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink ${className}`}
        {...props}
      />
    );
  },
);

export default OChon;
