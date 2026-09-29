"use client";

/**
 * Popover NỔI neo vào một phần tử (29/09/2026 — Đổi lịch tại chỗ, Tuyền chốt).
 *
 * · ≥768px: hộp nổi rộng ~600px, bo `r-modal`, bóng `panel`, mũi tên chỉ về
 *   phần tử neo; mở ngay DƯỚI neo, căn mép phải (thiếu chỗ thì lật lên trên).
 * · <768px: thành BOTTOM SHEET dính đáy màn hình, có nền mờ.
 * · Đóng: bấm ra ngoài, Esc, hoặc nút ×.
 * · Thân cuộn trong hộp (cao tối đa ~52vh); `chan` dính đáy hộp.
 *
 * Vẽ qua portal ra `document.body`: bảng chứa neo thường có `overflow-auto`,
 * vẽ bên trong thì bị cắt. Toạ độ ghi vào biến CSS (`--neo-y`, `--neo-x`) bằng
 * ref — lớp Tailwind đọc biến, không có `style={{}}` trong JSX.
 */

import { X } from "lucide-react";
import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

const KHE = 8;
const khongTheoDoi = () => () => {};

export default function PopoverNeo({
  neo,
  onDong,
  dau,
  chan,
  children,
}: {
  /** Phần tử neo (dòng khách, khung vàng…). null → canh giữa đầu màn. */
  neo: HTMLElement | null;
  onDong: () => void;
  /** Đầu hộp — tiêu đề (id gắn cho aria-labelledby). */
  dau: ReactNode;
  /** Chân hộp, dính đáy. */
  chan?: ReactNode;
  children: ReactNode;
}) {
  const hopRef = useRef<HTMLDivElement>(null);
  const tieuDeId = useId();
  const [tren, setTren] = useState(false);
  // Portal chỉ khi đã ở trình duyệt (trang dựng sẵn ở máy chủ không có document).
  const coThe = useSyncExternalStore(khongTheoDoi, () => true, () => false);

  useLayoutEffect(() => {
    const hop = hopRef.current;
    if (!hop) return;
    function dat() {
      if (!hop) return;
      const cao = hop.offsetHeight;
      const r = neo?.getBoundingClientRect();
      const duoi = r ? r.bottom + KHE : KHE * 8;
      const phai = r ? Math.max(window.innerWidth - r.right, KHE * 2) : KHE * 2;
      let y = duoi;
      let lat = false;
      if (r && duoi + cao > window.innerHeight - KHE && r.top - KHE - cao >= KHE) {
        y = r.top - KHE - cao;
        lat = true;
      } else if (duoi + cao > window.innerHeight - KHE) {
        y = Math.max(KHE, window.innerHeight - KHE - cao);
      }
      hop.style.setProperty("--neo-y", `${Math.round(y)}px`);
      hop.style.setProperty("--neo-x", `${Math.round(phai)}px`);
      setTren(lat);
    }
    dat();
    const quan = new ResizeObserver(dat);
    quan.observe(hop);
    window.addEventListener("resize", dat);
    window.addEventListener("scroll", dat, true);
    return () => {
      quan.disconnect();
      window.removeEventListener("resize", dat);
      window.removeEventListener("scroll", dat, true);
    };
  }, [neo, coThe]);

  useEffect(() => {
    function esc(e: KeyboardEvent) {
      if (e.key === "Escape") onDong();
    }
    function ngoai(e: PointerEvent) {
      const t = e.target as Node | null;
      if (!t) return;
      if (hopRef.current?.contains(t)) return;
      if (neo?.contains(t)) return;
      onDong();
    }
    window.addEventListener("keydown", esc);
    document.addEventListener("pointerdown", ngoai);
    return () => {
      window.removeEventListener("keydown", esc);
      document.removeEventListener("pointerdown", ngoai);
    };
  }, [neo, onDong]);

  if (!coThe) return null;
  return createPortal(
    <>
      {/* Nền mờ chỉ ở dạng bottom sheet (điện thoại). */}
      <div aria-hidden className="fixed inset-0 z-40 bg-ink/40 md:hidden" />
      <div
        ref={hopRef}
        role="dialog"
        aria-modal="false"
        aria-labelledby={tieuDeId}
        className={
          "fixed z-50 flex flex-col border border-hairline bg-surface shadow-panel " +
          // Điện thoại: bottom sheet.
          "inset-x-0 bottom-0 max-h-[85vh] rounded-t-2xl " +
          // Máy rộng: hộp nổi neo theo biến CSS.
          "md:inset-x-auto md:bottom-auto md:top-(--neo-y) md:right-(--neo-x) " +
          "md:w-150 md:max-w-[calc(100vw-2rem)] md:max-h-[80vh] md:rounded-2xl"
        }
      >
        {/* Mũi tên chỉ về dòng neo (máy rộng). */}
        {neo ? (
          <span
            aria-hidden
            className={`absolute right-6 hidden size-3 rotate-45 border-hairline bg-surface md:block ${
              tren ? "-bottom-1.5 border-b border-r" : "-top-1.5 border-l border-t"
            }`}
          />
        ) : null}
        <div className="flex items-start justify-between gap-3 border-b border-hairline px-4 py-3">
          <div id={tieuDeId} className="min-w-0 flex-1">
            {dau}
          </div>
          <button
            type="button"
            onClick={onDong}
            aria-label="Đóng"
            className="shrink-0 rounded-control p-1 text-ink-muted hover:bg-surface-sunken hover:text-ink"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 md:max-h-[52vh]">{children}</div>
        {chan ? (
          <div className="border-t border-hairline bg-surface-muted px-4 py-3 max-md:pb-[max(0.75rem,env(safe-area-inset-bottom))] md:rounded-b-2xl">
            {chan}
          </div>
        ) : null}
      </div>
    </>,
    document.body,
  );
}
