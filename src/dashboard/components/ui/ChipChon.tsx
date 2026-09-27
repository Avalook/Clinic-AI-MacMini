"use client";

/**
 * Hàng CHIP CHỌN — chọn MỘT trong vài mục nhỏ ngay trong thẻ (bản giao diện mẫu
 * `.chip-luot`, M/style.css:463-465: "Lần 1 · Lần 2 …" xem lại lần chỉ định cũ).
 *
 * Khác `ThanhTab`: tab đổi cả vùng nội dung của màn; chip chọn chỉ lọc một danh
 * sách trong thẻ, nên nhỏ và nằm cạnh tiêu đề. Chọn = nền brand đặc chữ trắng;
 * chưa chọn = nền chìm, hover teal nhạt. Bo `r-chip`, chữ `meta` đậm (DESIGN.md
 * §5). Dưới 640px cao 40px (ô bấm điện thoại — DESIGN.md §7), từ 640px cao 24px
 * như bản mẫu.
 */

export interface MucChipChon<T extends string | number> {
  ma: T;
  nhan: string;
  /** Chú thích khi rê chuột (vd "Xem lại lần 1 (chỉ xem)"). */
  title?: string;
  /** Chấm nhắc "có thứ mới ở mục này" (vd kết quả chưa xem ở lần cũ). */
  nhac?: boolean;
}

export default function ChipChon<T extends string | number>({
  muc,
  chon,
  onChon,
  nhan,
}: {
  muc: readonly MucChipChon<T>[];
  chon: T;
  onChon: (ma: T) => void;
  /** aria-label của cả hàng. */
  nhan: string;
}) {
  return (
    <div role="group" aria-label={nhan} className="flex flex-wrap items-center gap-1.5">
      {muc.map((m) => {
        const dang = m.ma === chon;
        return (
          <button
            key={String(m.ma)}
            type="button"
            aria-pressed={dang}
            title={m.title}
            onClick={() => onChon(m.ma)}
            className={`inline-flex h-10 items-center gap-1.5 rounded-chip px-2 text-meta font-semibold sm:h-6 ${
              dang
                ? "bg-brand-600 text-white"
                : "bg-surface-sunken text-ink-muted hover:bg-brand-50 hover:text-brand-700"
            }`}
          >
            {m.nhan}
            {m.nhac ? (
              <span
                aria-label="có mục mới chưa xem"
                className={`size-1.5 rounded-full ${dang ? "bg-white" : "bg-success"}`}
              />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
