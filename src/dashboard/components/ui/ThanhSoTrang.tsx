"use client";

/**
 * THANH SỐ TRANG — "‹ Trước  1 … 4 5 [6] 7 8 … 175  Sau ›" (06/10/2026, màn
 * Danh sách bệnh nhân: ~8.700 hồ sơ, 50 hồ sơ một trang).
 *
 * Dãy số tính ở `lib/so-trang.ts` (thuần, có bài kiểm). Màn hẹp (dưới 640px)
 * chỉ còn trang đang xem ± 1 và hai mũi tên không chữ, nút cao 40px (DESIGN.md
 * §7) — không cuộn ngang ở 375px; vẫn `flex-wrap` phòng chữ số dài. `hep` ép
 * dáng hẹp ở mọi cỡ (cột danh sách cạnh hồ sơ chỉ rộng ~300px).
 *
 * Một trang thì không vẽ gì: phòng khám 30 khách không cần nhìn "1".
 */

import { ChevronLeft, ChevronRight } from "lucide-react";
import { buttonClass } from "./Button";
import { cacSoTrang } from "../../lib/so-trang";

const O = "min-w-10 sm:h-8 sm:min-w-8 sm:px-2.5 sm:text-body tabular-nums";

export default function ThanhSoTrang({
  trang,
  soTrang,
  onChon,
  nhan = "Chuyển trang",
  hep = false,
  dangTai = false,
}: {
  trang: number;
  soTrang: number;
  onChon: (so: number) => void;
  /** aria-label của thanh. */
  nhan?: string;
  /** Ép dáng hẹp (trang ± 1, mũi tên không chữ) ở mọi cỡ màn. */
  hep?: boolean;
  /** Đang tải trang mới — khoá nút để không bấm chồng. */
  dangTai?: boolean;
}) {
  if (!(soTrang > 1)) return null;
  // Dáng hẹp ép buộc: bỏ hẳn mục rộng. Còn lại: mục rộng ẩn dưới 640px
  // (`max-sm:hidden` — biến thể đứng SAU `inline-flex` của nút nên thắng).
  const muc = cacSoTrang(trang, soTrang).filter((m) => !hep || m.hep);
  const anRong = (m: { hep: boolean }) => (m.hep ? "" : "max-sm:hidden");
  const chu = hep ? "sr-only" : "sr-only sm:not-sr-only";
  return (
    <nav aria-label={nhan} className="flex flex-wrap items-center justify-center gap-1">
      <button
        type="button"
        disabled={trang <= 1 || dangTai}
        onClick={() => onChon(trang - 1)}
        className={`${buttonClass("secondary", "lg")} ${O}`}
      >
        <ChevronLeft size={16} aria-hidden="true" />
        <span className={chu}>Trước</span>
      </button>
      {muc.map((m) =>
        m.loai === "cach" ? (
          <span
            key={m.khoa}
            aria-hidden="true"
            className={`${anRong(m)} inline-flex h-8 items-center px-1 text-meta text-ink-faint`}
          >
            …
          </span>
        ) : (
          <button
            key={m.so}
            type="button"
            disabled={dangTai && m.so !== trang}
            aria-current={m.so === trang ? "page" : undefined}
            aria-label={`Trang ${m.so}`}
            onClick={() => m.so !== trang && onChon(m.so)}
            className={`${buttonClass(m.so === trang ? "primary" : "secondary", "lg")} ${O} ${anRong(m)}`}
          >
            {m.so}
          </button>
        ),
      )}
      <button
        type="button"
        disabled={trang >= soTrang || dangTai}
        onClick={() => onChon(trang + 1)}
        className={`${buttonClass("secondary", "lg")} ${O}`}
      >
        <span className={chu}>Sau</span>
        <ChevronRight size={16} aria-hidden="true" />
      </button>
    </nav>
  );
}
