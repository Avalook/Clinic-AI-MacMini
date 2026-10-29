import type { ReactNode } from "react";
import { sdtDoc } from "../../lib/sdt";

/**
 * TÊN KHÁCH · SĐT trên một dòng, MÃ KHÁCH ở dòng dưới — mọi chỗ hiện khách
 * (Tuyền 27/10/2026: "SĐT kèm theo người cho tiện nhìn, tìm cho dễ").
 *
 * Một component để mọi màn cùng thứ tự, cùng cách viết số ("0900 007 126").
 * Thiếu SĐT / mã thì ẩn phần ấy. `cuoiDong` gắn thêm chip ngay sau SĐT (số
 * lượt, loại khám…) mà không phá thứ tự tên · SĐT.
 */
export default function TenKhachSdt({
  ten,
  sdt,
  ma,
  cuoiDong,
  tenClassName = "font-semibold text-ink",
  className = "",
}: {
  ten: ReactNode;
  sdt?: string | number | null;
  ma?: string | null;
  cuoiDong?: ReactNode;
  /** Cỡ / màu chữ của tên — mỗi màn giữ cỡ chữ tên như cũ. */
  tenClassName?: string;
  className?: string;
}) {
  const so = sdtDoc(sdt);
  return (
    <div className={`min-w-0 ${className}`}>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className={`min-w-0 break-words ${tenClassName}`}>{ten}</span>
        {/* SĐT đậm trên nền nhạt — mắt bắt ngay khi dò khách (Tuyền 29/10/2026:
            xám mảnh khó thấy). Cùng tông chip SĐT ở đầu thẻ khách Bàn khám. */}
        {so ? (
          <span className="whitespace-nowrap rounded-chip bg-brand-50 px-1.5 text-body font-semibold tabular-nums text-brand-700">
            {so}
          </span>
        ) : null}
        {cuoiDong}
      </div>
      {ma ? <div className="text-meta tabular-nums text-ink-faint">{ma}</div> : null}
    </div>
  );
}
