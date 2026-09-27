// TIÊU ĐỀ KHỐI của phiếu khám — bản giao diện mẫu `.khoi` (M/style.css:47-50):
// ô vuông 32 bo 8 nền brand-600 chữ trắng + h2 22px/600 + câu phụ dạt phải.
// Dùng chung cho ba khối phiếu bác sĩ chính (1 · 2 · 3) và khối "✎ Bác sĩ tư
// vấn" của bàn tư vấn — một chỗ khai, không chép chuỗi class.

import type { ReactNode } from "react";

export default function TieuDeKhoi({
  so,
  ten,
  phu,
  phuLuonHien = false,
}: {
  /** Số khối, hoặc "✎" ở bàn tư vấn. */
  so: ReactNode;
  ten: string;
  phu?: ReactNode;
  /** Mặc định câu phụ ẩn dưới 640px (nhường chỗ cho tên khối). */
  phuLuonHien?: boolean;
}) {
  return (
    <div className="flex scroll-mt-20 items-center gap-3 pt-4">
      <span className="grid size-8 shrink-0 place-items-center rounded-control bg-brand-600 text-emph font-semibold text-white">
        {so}
      </span>
      <h2 className="text-title font-semibold text-ink sm:text-hero">{ten}</h2>
      {phu ? (
        <span className={`ml-auto text-meta text-ink-muted ${phuLuonHien ? "" : "hidden sm:inline"}`}>{phu}</span>
      ) : null}
    </div>
  );
}
