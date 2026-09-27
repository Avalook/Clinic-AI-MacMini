"use client";

/**
 * Dải mốc theo THỜI GIAN — "khách đã đi qua đâu, chờ bao lâu giữa hai chặng".
 *
 * Khác `Stepper`: Stepper trả lời "đang ở bước nào" của MỘT quy trình cố định;
 * Timeline trả lời "mất bao lâu" — nhãn nằm TRÊN ĐOẠN NỐI giữa hai mốc (khoảng
 * chờ, "đang 12 phút"), vì khoảng chờ mới là thứ người ở bàn khám hỏi (bản giao
 * diện mẫu Tuyền duyệt 26/09/2026).
 *
 * Tông Y HỆT bản mẫu (27/09/2026): mốc xong chấm brand đặc + đoạn nối brand-100;
 * mốc đang diễn ra vòng xanh "đang làm" + đoạn nối gạch đứt cùng màu; mốc chưa
 * tới vòng xám. Nhãn khoảng chờ là một VIÊN nền trắng ngồi trên đoạn nối.
 *
 * Dải dài hơn khung: lăn chuột dọc = trượt ngang (tới mép thì trả lại cho trang
 * cuộn dọc), kéo chuột cũng trượt, mép còn nội dung thì mờ dần, và tự cuộn tới
 * mốc đang diễn ra để người dùng không bỏ lỡ. Điện thoại: vuốt như thường.
 * Component chỉ VẼ; nhãn đoạn nối do nơi gọi tính (lib/hanh-trinh).
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";

export type TrangThaiMoc = "xong" | "dang" | "chua";

export interface MocTimeline {
  khoa: string;
  ten: string;
  /** Nơi / người: "Lễ tân", "Phòng siêu âm · Đối tác". */
  noi?: string;
  /** "08:02", "08:20 → 08:35", "Lần 1 09:40 · Lần 2 10:20". */
  gio?: string;
  trangThai: TrangThaiMoc;
}

export interface DoanTimeline {
  /** "15 phút", "chờ 8 phút", "hôm trước"; null = không ghi. */
  nhan: string | null;
  trangThai: TrangThaiMoc;
}

const CHAM: Record<TrangThaiMoc, string> = {
  xong: "bg-brand-600",
  dang: "bg-surface ring-4 ring-inset ring-status-in-progress",
  chua: "bg-surface ring-2 ring-inset ring-line-strong",
};

const DOAN: Record<TrangThaiMoc, string> = {
  xong: "border-t-2 border-brand-100",
  dang: "border-t-2 border-dashed border-status-in-progress",
  chua: "border-t-2 border-hairline",
};

const NHAN_DOAN: Record<TrangThaiMoc, string> = {
  xong: "text-ink-soft",
  dang: "text-status-in-progress",
  chua: "text-ink-faint",
};

const TEN: Record<TrangThaiMoc, string> = {
  xong: "font-semibold text-ink",
  dang: "font-semibold text-status-in-progress",
  chua: "font-medium text-ink-faint",
};

export default function Timeline({
  moc,
  doan,
  dau,
  nhanAria = "Hành trình",
}: {
  moc: MocTimeline[];
  /** Đoạn nối SAU mốc thứ i (độ dài = moc.length - 1). */
  doan: DoanTimeline[];
  /** Dòng trên dải — thường là "Đang ở …". */
  dau?: ReactNode;
  nhanAria?: string;
}) {
  const day = useRef<HTMLOListElement>(null);
  const [mep, setMep] = useState({ trai: false, phai: false });

  const doMep = useCallback(() => {
    const el = day.current;
    if (!el) return;
    const trai = el.scrollLeft > 2;
    const phai = el.scrollLeft + el.clientWidth < el.scrollWidth - 2;
    setMep((c) => (c.trai === trai && c.phai === phai ? c : { trai, phai }));
  }, []);

  // Lăn chuột dọc → trượt ngang. Phải là trình nghe KHÔNG thụ động (React gắn
  // onWheel thụ động nên không chặn được trang cuộn theo).
  useEffect(() => {
    const el = day.current;
    if (!el) return;
    const lan = (e: WheelEvent) => {
      if (el.scrollWidth <= el.clientWidth) return;
      const d = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
      const max = el.scrollWidth - el.clientWidth;
      // Tới mép rồi → trả lại cho trang cuộn dọc, không "nuốt" bánh xe.
      if ((d < 0 && el.scrollLeft <= 0) || (d > 0 && el.scrollLeft >= max - 1)) return;
      e.preventDefault();
      el.scrollLeft += d;
    };
    el.addEventListener("wheel", lan, { passive: false });
    const co = new ResizeObserver(doMep);
    co.observe(el);
    return () => {
      el.removeEventListener("wheel", lan);
      co.disconnect();
    };
  }, [doMep]);

  // Kéo bằng chuột (cảm ứng đã tự vuốt được).
  const keo = useRef<{ x: number; l: number } | null>(null);
  const [dangKeo, setDangKeo] = useState(false);

  // Tự cuộn tới mốc ĐANG diễn ra (mốc "dang" cuối cùng) mỗi khi dải đổi.
  const khoaDang = moc.reduce((k, m) => (m.trangThai === "dang" ? m.khoa : k), "");
  useLayoutEffect(() => {
    const el = day.current;
    if (!el) return;
    const li = khoaDang ? el.querySelector<HTMLElement>(`[data-khoa="${CSS.escape(khoaDang)}"]`) : null;
    if (li) el.scrollLeft = li.offsetLeft - (el.clientWidth - li.offsetWidth) / 2;
    doMep();
  }, [khoaDang, moc.length, doMep]);

  return (
    <div className="space-y-3">
      {dau}
      <ol
        ref={day}
        aria-label={nhanAria}
        tabIndex={0}
        data-mep-trai={mep.trai ? "" : undefined}
        data-mep-phai={mep.phai ? "" : undefined}
        onScroll={doMep}
        onPointerDown={(e) => {
          if (e.pointerType !== "mouse" || e.button !== 0) return;
          keo.current = { x: e.clientX, l: e.currentTarget.scrollLeft };
        }}
        onPointerMove={(e) => {
          const k = keo.current;
          if (!k) return;
          const dx = e.clientX - k.x;
          if (!dangKeo && Math.abs(dx) > 3) {
            setDangKeo(true);
            e.currentTarget.setPointerCapture(e.pointerId);
          }
          e.currentTarget.scrollLeft = k.l - dx;
        }}
        onPointerUp={() => {
          keo.current = null;
          setDangKeo(false);
        }}
        onPointerCancel={() => {
          keo.current = null;
          setDangKeo(false);
        }}
        className={`relative flex select-none overflow-x-auto [scrollbar-width:none] focus-visible:outline-2 focus-visible:outline-brand-100 [&::-webkit-scrollbar]:hidden data-[mep-phai]:mask-r-from-[calc(100%-3rem)] data-[mep-trai]:mask-l-from-[calc(100%-3rem)] ${
          dangKeo ? "cursor-grabbing" : "cursor-grab"
        }`}
      >
        {moc.map((m, i) => {
          const d = doan[i];
          const sau = i < moc.length - 1;
          return (
            <li
              key={m.khoa}
              data-khoa={m.khoa}
              className="relative flex min-w-37 shrink-0 grow basis-37 flex-col gap-0.5 pr-2 pt-11"
            >
              <span aria-hidden className={`absolute left-0 top-6 z-10 size-3.5 rounded-full ${CHAM[m.trangThai]}`} />
              {sau ? (
                // Đoạn nối từ sau chấm này tới chấm kế; nhãn khoảng chờ là viên
                // ngồi TRÊN đường, ở giữa đoạn.
                <span aria-hidden className={`absolute left-3.5 right-0 top-7.5 ${DOAN[d?.trangThai ?? "chua"]}`}>
                  {d?.nhan ? (
                    <span
                      className={`absolute bottom-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-chip bg-surface px-1 text-meta font-semibold ${
                        NHAN_DOAN[d.trangThai]
                      }`}
                    >
                      {d.nhan}
                    </span>
                  ) : null}
                </span>
              ) : null}
              {d?.nhan && sau ? <span className="sr-only">{`Sau mốc: ${d.nhan}.`}</span> : null}
              <p className={`text-body ${TEN[m.trangThai]}`}>{m.ten}</p>
              {m.noi ? <p className="text-meta text-ink-muted">{m.noi}</p> : null}
              <p className="text-meta tabular-nums text-ink-soft">{m.gio || "—"}</p>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
