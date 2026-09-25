"use client";

/**
 * Công tắc bật / tắt (switch) — dùng cho màn Phân quyền theo lego (25/09/2026).
 *
 * `role="switch"` + `aria-checked` để trình đọc màn hình nói đúng "đang bật /
 * đang tắt". Vùng bấm tối thiểu min-h-10 như mọi nút khác (DESIGN.md §5).
 * `mot_phan`: trạng thái thứ ba — có vài khối của lego nhưng chưa đủ.
 */

export default function CongTac({
  bat,
  motPhan = false,
  onDoi,
  disabled = false,
  nhan,
}: {
  bat: boolean;
  motPhan?: boolean;
  onDoi: (bat: boolean) => void;
  disabled?: boolean;
  /** aria-label — tên việc mà công tắc bật / tắt. */
  nhan: string;
}) {
  const nen = bat ? "bg-brand-600" : motPhan ? "bg-warning" : "bg-line";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={bat}
      aria-label={nhan}
      disabled={disabled}
      onClick={() => onDoi(!bat)}
      className="inline-flex min-h-10 shrink-0 items-center disabled:opacity-50"
    >
      <span
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${nen}`}
      >
        <span
          className={`inline-block size-5 rounded-full bg-surface shadow-card transition-transform ${
            bat ? "translate-x-5" : "translate-x-0.5"
          }`}
        />
      </span>
    </button>
  );
}
