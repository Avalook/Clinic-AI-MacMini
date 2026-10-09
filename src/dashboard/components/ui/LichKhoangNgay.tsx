"use client";

/**
 * Ô CHỌN KHOẢNG NGÀY GỌN — một nút + lịch thả xuống (27/09/2026, Tuyền: "cho cái
 * form lịch đã có ở thanh menu vào luôn cho tiện").
 *
 * Cùng dáng lịch nhỏ ở thanh trên (`GlobalHeader`): tháng + ‹ ›, hàng CN…T7,
 * lưới ngày tròn. Thêm: hàng chip nhanh (Hôm nay · 7 ngày …) và chọn KHOẢNG —
 * bấm ngày đầu rồi ngày cuối (bấm hai lần cùng một ngày = một ngày). Thay dải
 * ngày ngang `ThanhNgay` ở chỗ cần gọn (màn Quản lý khách hàng); `ThanhNgay`
 * vẫn giữ cho các màn khác.
 *
 * Ngày là chuỗi yyyy-mm-dd theo giờ VN do màn truyền vào (`homNay`) — không đọc
 * giờ máy ở đây.
 */

import { Calendar as CalendarIcon, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { NHANH, khoangNhanh, maCuaKhoang, nhanKhoang, type Khoang } from "@/lib/thanh-ngay";

const THANG = [
  "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4", "Tháng 5", "Tháng 6",
  "Tháng 7", "Tháng 8", "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12",
];

function chuoi(y: number, m: number, d: number): string {
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

const CHIP = "inline-flex h-7 items-center rounded-control px-2.5 text-meta font-medium";
const CHIP_CHON = "bg-brand-600 text-white";
const CHIP_THUONG = "bg-surface-muted text-ink-soft hover:bg-surface-sunken";

export default function LichKhoangNgay({
  khoang,
  homNay,
  onChon,
  nhan = "Khoảng ngày",
  dangTai = false,
  ngayCham,
}: {
  /** null = tất cả. */
  khoang: Khoang | null;
  homNay: string;
  onChon: (k: Khoang | null) => void;
  nhan?: string;
  dangTai?: boolean;
  /** Ngày (yyyy-mm-dd) được chấm xanh dưới số — vd ngày khách có khám. */
  ngayCham?: ReadonlySet<string>;
}) {
  const [mo, setMo] = useState(false);
  const [dau, setDau] = useState<string | null>(null);
  const goc = (khoang?.den ?? homNay).split("-").map(Number);
  const [nam, setNam] = useState(goc[0] || 2026);
  const [thang, setThang] = useState((goc[1] || 1) - 1);
  const hop = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mo) return;
    const ra = (e: MouseEvent) => {
      if (hop.current && !hop.current.contains(e.target as Node)) setMo(false);
    };
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMo(false);
    };
    document.addEventListener("mousedown", ra);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", ra);
      document.removeEventListener("keydown", esc);
    };
  }, [mo]);

  const maDang = maCuaKhoang(khoang, homNay);
  const chon = (k: Khoang | null) => {
    setDau(null);
    setMo(false);
    onChon(k);
  };
  const bamNgay = (ngay: string) => {
    if (dau === null) {
      setDau(ngay);
      return;
    }
    chon(ngay < dau ? { tu: ngay, den: dau } : { tu: dau, den: ngay });
  };

  const soNgay = new Date(nam, thang + 1, 0).getDate();
  const thuDau = new Date(nam, thang, 1).getDay();
  const lui = () => (thang === 0 ? (setThang(11), setNam((y) => y - 1)) : setThang((m) => m - 1));
  const toi = () => (thang === 11 ? (setThang(0), setNam((y) => y + 1)) : setThang((m) => m + 1));

  const nhanNut =
    khoang === null
      ? "Tất cả ngày"
      : (NHANH.find((n) => n.ma === maDang)?.nhan ?? nhanKhoang(khoang));

  return (
    <div ref={hop} className="relative">
      <button
        type="button"
        aria-label={nhan}
        aria-expanded={mo}
        onClick={() => setMo((m) => !m)}
        className={`inline-flex h-8 items-center gap-1.5 rounded-control border border-line bg-surface px-3 text-meta font-medium text-ink hover:bg-surface-muted ${
          dangTai ? "opacity-60" : ""
        }`}
      >
        <CalendarIcon size={14} className="shrink-0 text-brand-600" aria-hidden="true" />
        <span>{nhanNut}</span>
        <ChevronDown size={13} className="text-ink-muted" aria-hidden="true" />
      </button>

      {mo ? (
        <div className="fixed inset-x-4 top-28 z-50 mx-auto max-w-72 rounded-2xl sm:absolute sm:inset-x-auto sm:left-0 sm:top-10 sm:w-72 border border-line bg-surface p-3 shadow-panel">
          <div className="mb-3 flex flex-wrap gap-1">
            {NHANH.map(({ ma, nhan: ten }) => (
              <button
                key={ma}
                type="button"
                aria-pressed={maDang === ma}
                onClick={() => chon(khoangNhanh(ma, homNay))}
                className={`${CHIP} ${maDang === ma ? CHIP_CHON : CHIP_THUONG}`}
              >
                {ten}
              </button>
            ))}
            <button
              type="button"
              aria-pressed={khoang === null}
              onClick={() => chon(null)}
              className={`${CHIP} ${khoang === null ? CHIP_CHON : CHIP_THUONG}`}
            >
              Tất cả
            </button>
          </div>

          <div className="mb-2 flex items-center justify-between">
            <span className="text-body font-semibold text-ink">
              {THANG[thang]} {nam}
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                aria-label="Tháng trước"
                onClick={lui}
                className="grid size-7 place-items-center rounded-control text-ink-muted hover:bg-surface-muted"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                type="button"
                aria-label="Tháng sau"
                onClick={toi}
                className="grid size-7 place-items-center rounded-control text-ink-muted hover:bg-surface-muted"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
          <div className="mb-1 grid grid-cols-7 text-center text-label font-semibold text-ink-muted">
            {["CN", "T2", "T3", "T4", "T5", "T6", "T7"].map((t) => (
              <span key={t}>{t}</span>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1 text-center text-meta">
            {Array.from({ length: thuDau }).map((_, i) => (
              <span key={`r${i}`} />
            ))}
            {Array.from({ length: soNgay }).map((_, i) => {
              const ngay = chuoi(nam, thang, i + 1);
              const tu = dau ?? khoang?.tu ?? null;
              const den = dau ? dau : (khoang?.den ?? null);
              const dauCuoi = ngay === tu || ngay === den;
              const giua = !dau && tu && den && ngay > tu && ngay < den;
              return (
                <button
                  key={ngay}
                  type="button"
                  aria-pressed={dauCuoi}
                  onClick={() => bamNgay(ngay)}
                  className={`grid size-8 place-items-center rounded-full font-medium ${
                    dauCuoi
                      ? "bg-brand-600 font-semibold text-white"
                      : giua
                        ? "bg-brand-50 text-brand-700"
                        : ngay === homNay
                          ? "text-brand-700 ring-1 ring-inset ring-brand-200 hover:bg-brand-50"
                          : "text-ink hover:bg-brand-50"
                  }`}
                >
                  <span className="relative">
                    {i + 1}
                    {ngayCham?.has(ngay) ? (
                      <span
                        aria-label="có khám"
                        className="absolute -bottom-1.5 left-1/2 size-1.5 -translate-x-1/2 rounded-full bg-success"
                      />
                    ) : null}
                  </span>
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-label text-ink-muted">
            {dau ? "Bấm ngày cuối (bấm lại cùng ngày = một ngày)." : "Bấm ngày đầu rồi ngày cuối."}
          </p>
        </div>
      ) : null}
    </div>
  );
}
