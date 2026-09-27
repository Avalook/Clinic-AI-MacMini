"use client";

/**
 * Ngăn gập — MỘT thành phần cho mọi "bấm tiêu đề để mở / thu lại" (đợt 3,
 * 27/09/2026). Trước đó mỗi chỗ tự viết `<details>` với một bộ class riêng.
 *
 * · Nút thật (`<button type="button">`, `aria-expanded`, `aria-controls`):
 *   Tab tới được, Enter / Space mở–đóng, trình đọc màn hình nói "đã mở / đã thu".
 * · Nội dung chỉ ẨN (`hidden`), không gỡ khỏi cây: ô đang gõ dở, dấu tick chưa
 *   lưu bên trong vẫn còn khi mở lại.
 * · `moSan`: mặc định lúc đầu; chuyển từ false sang true (vừa có dữ liệu) thì
 *   TỰ MỞ. Không tự đóng khi về false — không gập mất chỗ người ta đang gõ.
 * · `nhoKhoa`: nhớ lần đóng/mở cuối của NGƯỜI DÙNG (localStorage, đọc/ghi hỏng
 *   thì theo mặc định — `lib/ngan-gap.ts`). Đọc qua `useSyncExternalStore` với
 *   bản máy chủ = "chưa nhớ": trang dựng sẵn ở máy chủ không lệch lúc hydrate.
 *
 * Hai dáng: `the` — đầu thẻ con của phiếu (chữ `emph` đậm, câu phụ bên phải);
 * `dong` — một dòng chữ `meta` mờ trong thân thẻ (bảng phụ, danh sách phụ).
 */

import { ChevronRight } from "lucide-react";
import { useId, useState, useSyncExternalStore, type ReactNode } from "react";

import { docNhoGap, ghiNhoGap, moBanDau } from "@/lib/ngan-gap";

/** Kho nhớ chỉ đổi khi chính ngăn này bấm (đã giữ trong state) — không cần nghe. */
const khongTheoDoi = () => () => {};

export default function NganGap({
  tieuDe,
  phu,
  chip,
  moSan = false,
  nhoKhoa,
  co = "dong",
  children,
}: {
  tieuDe: ReactNode;
  /** Câu phụ bên phải (dáng `the`). */
  phu?: ReactNode;
  /** Chip cạnh tiêu đề — vd "3 ô đã điền". */
  chip?: ReactNode;
  moSan?: boolean;
  nhoKhoa?: string;
  co?: "the" | "dong";
  children: ReactNode;
}) {
  const id = useId();
  const daNho = useSyncExternalStore(
    khongTheoDoi,
    () => (nhoKhoa ? docNhoGap(nhoKhoa) : null),
    () => null,
  );
  // Lần bấm trong phiên màn này — có thì thắng cả nhớ lẫn mặc định.
  const [bam, setBam] = useState<boolean | null>(null);
  const mo = bam ?? moBanDau(daNho, moSan);
  // Theo `moSan` ngay lúc render (không qua effect): không vẽ một nhịp đóng.
  const [moSanTruoc, setMoSanTruoc] = useState(moSan);
  if (moSanTruoc !== moSan) {
    setMoSanTruoc(moSan);
    if (moSan && !mo) setBam(true);
  }

  const doi = () => {
    const moi = !mo;
    setBam(moi);
    if (nhoKhoa) ghiNhoGap(nhoKhoa, moi);
  };

  const the = co === "the";
  return (
    <div>
      <button
        type="button"
        aria-expanded={mo}
        aria-controls={id}
        onClick={doi}
        className={`flex w-full min-w-0 flex-wrap items-center gap-x-2 gap-y-1 rounded-control text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 ${
          the ? "min-h-10 sm:min-h-8" : "min-h-10 text-meta text-ink-muted hover:text-ink sm:min-h-8"
        }`}
      >
        <ChevronRight
          aria-hidden
          className={`size-4 shrink-0 text-ink-muted transition-transform duration-200 motion-reduce:transition-none ${
            mo ? "rotate-90" : ""
          }`}
        />
        <span className={the ? "text-emph font-semibold text-ink" : ""}>{tieuDe}</span>
        {chip}
        {phu ? <span className="ml-auto text-meta text-ink-muted">{phu}</span> : null}
      </button>
      <div id={id} hidden={!mo} className={the ? "mt-3 space-y-3" : "mt-2"}>
        {children}
      </div>
    </div>
  );
}
