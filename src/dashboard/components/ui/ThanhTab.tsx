"use client";

/**
 * Thanh tab chung — một dãy nút `role="tab"`, đúng kiểu các tab đã có ở Thu
 * ngân / Trưởng ca / Nhà thuốc (min-h-10, rounded-control, nền brand khi chọn).
 *
 * Chỉ vẽ thanh; nội dung từng tab do màn tự ẩn/hiện. Màn nào cần GIỮ trạng
 * thái của tab bị ẩn (bệnh án đang gõ dở) thì ẩn bằng class, đừng gỡ khỏi cây.
 */

export interface MucTab<T extends string> {
  ma: T;
  nhan: string;
  /** Dấu chấm nhắc "có việc ở tab này" (ví dụ kết quả mới cần đọc). */
  nhac?: boolean;
  /** Số đếm trong viên tròn cạnh nhãn (danh sách Tiếp đón 27/09 đợt 3:
   *  "Tất cả ⟨n⟩ · Chưa đến ⟨n⟩ · Đã check-in ⟨n⟩"). Không truyền = không vẽ. */
  dem?: number;
}

export default function ThanhTab<T extends string>({
  muc,
  chon,
  onChon,
  nhan,
  className = "",
}: {
  muc: readonly MucTab<T>[];
  chon: T;
  onChon: (ma: T) => void;
  /** aria-label của cả thanh. */
  nhan: string;
  className?: string;
}) {
  return (
    <div role="tablist" aria-label={nhan} className={`flex flex-wrap gap-1 ${className}`}>
      {muc.map((m) => {
        const dang = m.ma === chon;
        return (
          <button
            key={m.ma}
            type="button"
            role="tab"
            aria-selected={dang}
            onClick={() => onChon(m.ma)}
            className={`inline-flex min-h-10 items-center gap-1.5 rounded-control px-3 text-sm font-medium ${
              dang
                ? "bg-brand-600 text-white"
                : "bg-surface-muted text-ink-soft hover:bg-surface-sunken"
            }`}
          >
            {m.nhan}
            {m.dem != null ? (
              <span
                className={`inline-grid h-6 min-w-6 place-items-center rounded-full px-1.5 text-meta font-semibold tabular-nums ${
                  dang ? "bg-surface text-brand-700" : "bg-line-strong text-ink-soft"
                }`}
              >
                {m.dem}
              </span>
            ) : null}
            {m.nhac ? (
              <span
                aria-label="có việc cần xem"
                className={`size-2 rounded-full ${dang ? "bg-white" : "bg-warning"}`}
              />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
