"use client";

// Khung 2 cột "cùng 1 mặt phẳng": kéo THANH GIỮA → cột trái dãn thì cột phải co
// (tổng luôn = 100%, mượt, không nhảy layout). Dùng cho khu check-in (danh sách |
// hồ sơ lâm sàng). Trên mobile xếp DỌC (không có thanh kéo).
//
// Bề rộng cột trái áp bằng INLINE style (flex-basis %) thay vì class Tailwind
// arbitrary — Tailwind không sinh class flex-basis động được (và còn quét cả
// comment tìm class, nên ở đây tránh viết cú pháp ngoặc-vuông kẻo nó sinh CSS
// hỏng làm vỡ dev build). Chỉ áp khi màn hình rộng (md+, matchMedia) để mobile
// vẫn xếp dọc bình thường.

import { useCallback, useEffect, useRef, useState } from "react";

export default function SplitPane({
  left,
  right,
  initialLeftPct = 55,
  minPct = 28,
  maxPct = 78,
  className = "",
}: {
  left: React.ReactNode;
  right: React.ReactNode;
  initialLeftPct?: number;
  minPct?: number;
  maxPct?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const [leftPct, setLeftPct] = useState(initialLeftPct);
  const [isWide, setIsWide] = useState(false);
  const [active, setActive] = useState(false); // đang kéo thanh giữa

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const update = () => setIsWide(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  const apply = useCallback(
    (clientX: number) => {
      const el = ref.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const pct = ((clientX - rect.left) / rect.width) * 100;
      setLeftPct(Math.max(minPct, Math.min(maxPct, pct)));
    },
    [minPct, maxPct],
  );

  const startDrag = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      dragging.current = true;
      setActive(true);
      document.body.style.userSelect = "none";
      document.body.style.cursor = "col-resize";
      const move = (ev: PointerEvent) => {
        if (dragging.current) apply(ev.clientX);
      };
      const up = () => {
        dragging.current = false;
        setActive(false);
        document.body.style.userSelect = "";
        document.body.style.cursor = "";
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    },
    [apply],
  );

  return (
    <div ref={ref} className={"flex flex-col md:flex-row " + className}>
      <div
        className="min-w-0 md:overflow-auto"
        style={isWide ? { flexBasis: `${leftPct}%` } : undefined}
      >
        {left}
      </div>

      {/* Thanh kéo giữa — hit-area rộng (12px), line mảnh 1px, sáng + dày lên khi
          hover/kéo (kiểu Linear). Chỉ desktop; mobile xếp dọc nên ẩn. */}
      <div
        onPointerDown={startDrag}
        role="separator"
        aria-orientation="vertical"
        aria-label="Kéo để chia lại độ rộng 2 bảng"
        className="group relative hidden w-3 shrink-0 cursor-col-resize touch-none items-stretch justify-center md:flex"
      >
        <span
          className={
            "my-2 rounded-full transition-all duration-150 " +
            (active
              ? "w-[3px] bg-brand-700"
              : "w-px bg-[#f0d4e2] group-hover:w-[3px] group-hover:bg-brand-600")
          }
        />
      </div>

      <div className="mt-3 min-w-0 md:mt-0 md:flex-1 md:overflow-auto">
        {right}
      </div>
    </div>
  );
}
