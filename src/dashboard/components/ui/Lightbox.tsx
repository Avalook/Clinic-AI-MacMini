"use client";

/**
 * Hộp xem tệp — ảnh, video, PDF, tài liệu (lát 5, 26/09/2026). Từ 27/09 là HỘP
 * GIỮA MÀN bo 16 (DESIGN.md §4 `r-modal`), không còn phủ kín màn rộng.
 *
 * Bản giao diện mẫu Tuyền duyệt: lật trước/sau (nút + phím ←/→), lưới, dải ảnh
 * nhỏ, Tải về, Tải tất cả, PDF xem trong khung; ở phiếu khám thì CHIA ĐÔI —
 * kết quả bên trái, ảnh bên phải (`trai`), bấm "Chỉ xem ảnh" để ẩn bên trái.
 *
 * Trước đây mỗi màn tự vẽ một popup một-tệp (KhungTep). Nay một chỗ; màn nào
 * cần xem tệp thì dùng cái này.
 *
 * Esc đóng; khoá cuộn trang nền trong lúc mở; nút Đóng nhận focus lúc mở để
 * người dùng bàn phím không bị bỏ lại dưới lớp phủ.
 */

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronLeft, ChevronRight, FileText, X } from "lucide-react";

/** Nút trên nền tối của hộp (bản mẫu `.lb-b`): nền trắng 10%, chữ trắng, cao
 *  32 bo 8 — cỡ `md` của thang nút; nút sáng của `Button` chói trên nền tối. */
const NUT =
  "inline-flex h-8 items-center gap-1.5 whitespace-nowrap rounded-control bg-surface/10 px-3 " +
  "text-meta font-medium text-white transition-colors duration-100 hover:bg-surface/20 " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400";

export interface TepXem {
  id: string;
  /** Đường xem (đã xác thực). */
  src: string;
  ten: string;
  /** ANH · VIDEO · PDF · TAI_LIEU (Word/Excel). */
  loai: string;
  /** "Ảnh 2/5 · 09:40 · BS siêu âm". */
  phu?: string;
  /** Đường TẢI VỀ (lưu tệp); không có thì không hiện nút. */
  taiVe?: string;
}

function ONho({ t, lon = false }: { t: TepXem; lon?: boolean }) {
  if (t.loai === "ANH") {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- ảnh đi qua cửa XÁC THỰC; bộ tối ưu ảnh không mang cookie phiên.
      <img
        src={t.src}
        alt={t.ten}
        loading="lazy"
        className={`h-full w-full object-cover ${lon ? "" : "bg-ink"}`}
      />
    );
  }
  if (t.loai === "VIDEO") {
    return (
      <span className="relative block h-full w-full bg-ink">
        <video src={`${t.src}#t=0.8`} preload="metadata" muted playsInline className="h-full w-full object-cover" />
        <span aria-hidden className="absolute inset-0 flex items-center justify-center text-title text-white">
          ▶
        </span>
      </span>
    );
  }
  return (
    <span className="flex h-full w-full flex-col items-center justify-center gap-1 bg-surface p-1 text-ink-soft">
      <FileText className="size-5" aria-hidden />
      <span className="line-clamp-2 text-center text-label">{t.ten}</span>
    </span>
  );
}

function taiTep(ds: TepXem[]) {
  // Từng tệp một, cách nhau một nhịp — trình duyệt chặn loạt tải dồn cùng lúc.
  ds.forEach((t, i) => {
    if (!t.taiVe) return;
    setTimeout(() => {
      const a = document.createElement("a");
      a.href = t.taiVe!;
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      a.remove();
    }, i * 250);
  });
}

export default function Lightbox({
  tieuDe,
  phuDe,
  tep,
  batDau = 0,
  luoiBanDau = false,
  trai,
  veTaiLieu,
  onDong,
}: {
  tieuDe: string;
  phuDe?: string;
  tep: TepXem[];
  batDau?: number;
  luoiBanDau?: boolean;
  /** Có thì hộp CHIA ĐÔI: nội dung này bên trái (kết quả), tệp bên phải. */
  trai?: ReactNode;
  /** Vẽ tài liệu Word/Excel (xem tại chỗ) — không có thì hiện "Tải về". */
  veTaiLieu?: (t: TepXem) => ReactNode;
  onDong: () => void;
}) {
  const [i, setI] = useState(() => Math.min(Math.max(batDau, 0), Math.max(tep.length - 1, 0)));
  const [luoi, setLuoi] = useState(luoiBanDau);
  const [hienTrai, setHienTrai] = useState(true);
  const nutDong = useRef<HTMLButtonElement>(null);
  const n = tep.length;
  const t = tep[Math.min(i, n - 1)];

  const lui = useCallback(() => setI((x) => (x - 1 + n) % n), [n]);
  const toi = useCallback(() => setI((x) => (x + 1) % n), [n]);

  useEffect(() => {
    nutDong.current?.focus();
    const cu = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = cu;
    };
  }, []);

  useEffect(() => {
    const phim = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDong();
      else if (!luoi && n > 1 && e.key === "ArrowRight") toi();
      else if (!luoi && n > 1 && e.key === "ArrowLeft") lui();
    };
    document.addEventListener("keydown", phim);
    return () => document.removeEventListener("keydown", phim);
  }, [onDong, luoi, n, toi, lui]);

  const chia = trai !== undefined && hienTrai;
  const nutToi = "rounded-control bg-surface/10 text-white hover:bg-surface/20";

  let xem: ReactNode;
  if (!t) {
    xem = (
      <div className="flex h-full items-center justify-center rounded-card bg-surface/10 p-6 text-center text-body text-white">
        Chưa có ảnh / video cho kết quả này
      </div>
    );
  } else if (luoi) {
    xem = (
      <ul className="grid grid-cols-2 gap-2 overflow-y-auto sm:grid-cols-3 lg:grid-cols-4">
        {tep.map((x, k) => (
          <li key={x.id}>
            <button
              type="button"
              onClick={() => {
                setI(k);
                setLuoi(false);
              }}
              className={`block aspect-square w-full overflow-hidden rounded-control ring-2 ${
                k === i ? "ring-brand-400" : "ring-transparent"
              }`}
              title={x.ten}
            >
              <ONho t={x} />
            </button>
          </li>
        ))}
      </ul>
    );
  } else {
    xem = (
      <div className="flex h-full min-h-0 flex-col gap-2">
        <div className="relative flex min-h-0 flex-1 items-center justify-center">
          {n > 1 ? (
            <button type="button" onClick={lui} aria-label="Tệp trước" className={`absolute left-0 z-10 p-2 ${nutToi}`}>
              <ChevronLeft className="size-6" aria-hidden />
            </button>
          ) : null}
          {t.loai === "ANH" ? (
            // eslint-disable-next-line @next/next/no-img-element -- như trên
            <img src={t.src} alt={t.ten} className="max-h-full max-w-full object-contain" />
          ) : t.loai === "VIDEO" ? (
            <video key={t.id} src={t.src} controls autoPlay playsInline className="max-h-full max-w-full" />
          ) : t.loai === "PDF" ? (
            <iframe key={t.id} src={t.src} title={t.ten} className="h-full w-full rounded-control bg-surface" />
          ) : veTaiLieu ? (
            <div className="max-h-full w-full overflow-auto rounded-control bg-surface">{veTaiLieu(t)}</div>
          ) : (
            <div className="rounded-card bg-surface p-6 text-center text-body text-ink">
              Không xem trước được loại tệp này — bấm “Tải về”.
            </div>
          )}
          {n > 1 ? (
            <button type="button" onClick={toi} aria-label="Tệp sau" className={`absolute right-0 z-10 p-2 ${nutToi}`}>
              <ChevronRight className="size-6" aria-hidden />
            </button>
          ) : null}
        </div>
        <p className="flex flex-wrap items-baseline gap-x-2 text-meta text-white/80">
          <span className="min-w-0 truncate font-semibold text-white">{t.ten}</span>
          <span>
            {i + 1}/{n}
            {t.phu ? ` · ${t.phu}` : ""}
          </span>
        </p>
        {n > 1 ? (
          <ul className="flex gap-1.5 overflow-x-auto pb-1">
            {tep.map((x, k) => (
              <li key={x.id} className="shrink-0">
                <button
                  type="button"
                  onClick={() => setI(k)}
                  aria-label={`Xem ${x.ten}`}
                  className={`block size-14 overflow-hidden rounded-control ring-2 ${
                    k === i ? "ring-brand-400" : "ring-transparent opacity-70 hover:opacity-100"
                  }`}
                >
                  <ONho t={x} />
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }

  return (
    // HỘP GIỮA MÀN bo 16 (27/09/2026, Y HỆT bản mẫu `.lb`): màn rộng thấy trang
    // phía sau qua lớp phủ tối, bấm lớp phủ là đóng; điện thoại (<640) hộp phủ
    // gần kín màn, không bo — chỗ nào cũng dành cho ảnh.
    <div role="dialog" aria-modal="true" aria-label={tieuDe} className="fixed inset-0 z-50 flex items-center justify-center sm:p-6">
      <div aria-hidden className="absolute inset-0 bg-ink/80" onClick={onDong} />
      <div
        className={`relative flex h-full w-full flex-col overflow-hidden bg-ink text-white shadow-panel sm:max-h-208 sm:rounded-2xl ${
          chia ? "sm:max-w-330" : "sm:max-w-275"
        }`}
      >
        <div className="flex flex-wrap items-center gap-2 border-b border-surface/10 px-4 py-3">
          {/* Điện thoại: tiêu đề một dòng riêng, không bị cụm nút ép còn "Ản…". */}
          <div className="min-w-0 basis-full sm:basis-0 sm:flex-1">
            <p className="truncate text-emph font-semibold">
              {tieuDe}
              {phuDe || n ? (
                <span className="ml-2 text-meta font-normal text-white/70">
                  {[phuDe, n ? `${n} tệp` : null].filter(Boolean).join(" · ")}
                </span>
              ) : null}
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {trai !== undefined ? (
              <button type="button" onClick={() => setHienTrai((x) => !x)} className={NUT}>
                {hienTrai ? "Chỉ xem ảnh" : "Hiện kết quả"}
              </button>
            ) : null}
            {n > 1 ? (
              <button type="button" onClick={() => setLuoi((x) => !x)} className={NUT}>
                {luoi ? "Xem từng tấm" : `Lưới (${n})`}
              </button>
            ) : null}
            {/* IN (29/09/2026 — "file kết quả mọi chỗ tải/in được"): mở tệp
                gốc ở thẻ mới, in bằng trình duyệt (ảnh, PDF). */}
            {t && !luoi && t.src ? (
              <a href={t.src} target="_blank" rel="noopener" className={NUT}>
                Mở / In
              </a>
            ) : null}
            {t && !luoi && t.taiVe ? (
              <a href={t.taiVe} rel="noopener" className={NUT}>
                Tải về
              </a>
            ) : null}
            {n > 1 ? (
              <button type="button" onClick={() => taiTep(tep)} className={NUT}>
                Tải tất cả
              </button>
            ) : null}
            <button ref={nutDong} type="button" onClick={onDong} aria-label="Đóng" className={`${NUT} w-8 justify-center px-0`}>
              <X className="size-4" aria-hidden />
            </button>
          </div>
        </div>
        <div
          className={`grid min-h-0 flex-1 grid-cols-1 ${
            chia ? "grid-rows-[minmax(0,2fr)_minmax(0,3fr)] lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:grid-rows-1" : ""
          }`}
        >
          {chia ? (
            <aside className="min-h-0 min-w-0 overflow-y-auto bg-surface p-4 text-body text-ink">{trai}</aside>
          ) : null}
          <div className="min-h-0 min-w-0 p-3 sm:p-4">{xem}</div>
        </div>
      </div>
    </div>
  );
}
