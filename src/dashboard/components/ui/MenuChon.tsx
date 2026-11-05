/**
 * Nút chọn THẢ XUỐNG: "Nhãn: Đang chọn ▾" + danh sách (05/11/2026 — bản mẫu bàn XN,
 * "Đối tác: TrueMedicine ▾"). Dùng khi lựa chọn là MỘT bộ lọc đứng ở góc màn, số mục
 * có thể nhiều (chip sẽ tràn dòng).
 *
 * · Đóng: chọn một mục, bấm ra ngoài, hoặc Esc (trả focus về nút).
 * · Bàn phím: mũi tên lên/xuống trong danh sách; Enter/Space chọn.
 * · Chỉ chọn — không biết luật gì; danh sách do nơi gọi đưa (máy chủ trả).
 */

import { ChevronDown } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

export interface MucMenu {
  ma: string;
  nhan: string;
}

export default function MenuChon({
  nhan,
  muc,
  chon,
  onChon,
}: {
  nhan: string;
  muc: MucMenu[];
  chon: string;
  onChon: (ma: string) => void;
}) {
  const [mo, setMo] = useState(false);
  const goc = useRef<HTMLDivElement>(null);
  const nut = useRef<HTMLButtonElement>(null);
  const id = useId();
  const dang = muc.find((m) => m.ma === chon) ?? muc[0];

  useEffect(() => {
    if (!mo) return;
    const ngoai = (e: MouseEvent) => {
      if (goc.current && !goc.current.contains(e.target as Node)) setMo(false);
    };
    document.addEventListener("mousedown", ngoai);
    return () => document.removeEventListener("mousedown", ngoai);
  }, [mo]);

  function phim(e: React.KeyboardEvent<HTMLUListElement>) {
    const nuts = [...(e.currentTarget.querySelectorAll("button") as NodeListOf<HTMLButtonElement>)];
    const i = nuts.indexOf(document.activeElement as HTMLButtonElement);
    if (e.key === "Escape") {
      setMo(false);
      nut.current?.focus();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      nuts[Math.min(i + 1, nuts.length - 1)]?.focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      nuts[Math.max(i - 1, 0)]?.focus();
    }
  }

  return (
    <div ref={goc} className="relative">
      <button
        ref={nut}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={mo}
        aria-controls={id}
        onClick={() => setMo((x) => !x)}
        onKeyDown={(e) => e.key === "Escape" && setMo(false)}
        className="inline-flex min-h-10 items-center gap-1.5 rounded-control border border-line-strong bg-surface px-3 text-body font-semibold text-ink hover:bg-surface-sunken sm:min-h-9"
      >
        {nhan}: {dang?.nhan ?? "—"}
        <ChevronDown aria-hidden className="size-4 text-ink-muted" />
      </button>
      {mo ? (
        <ul
          id={id}
          role="listbox"
          aria-label={nhan}
          onKeyDown={phim}
          className="absolute right-0 top-full z-30 mt-1 min-w-full overflow-hidden rounded-card border border-line bg-surface py-1 shadow-card"
        >
          {muc.map((m) => (
            <li key={m.ma || "tat-ca"} role="option" aria-selected={m.ma === chon}>
              <button
                type="button"
                autoFocus={m.ma === chon}
                onClick={() => {
                  onChon(m.ma);
                  setMo(false);
                  nut.current?.focus();
                }}
                className={`flex w-full whitespace-nowrap px-3 py-2 text-left text-body ${
                  m.ma === chon ? "bg-brand-50 font-semibold text-brand-700" : "text-ink hover:bg-surface-sunken"
                }`}
              >
                {m.nhan}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
