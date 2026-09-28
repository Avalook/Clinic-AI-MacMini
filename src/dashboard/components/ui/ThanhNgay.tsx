"use client";

/**
 * Thanh ngày ngang — chọn khoảng ngày tra cứu bằng một cú bấm (Tuyền 27/09/2026:
 * "xem khách hôm qua, hôm kia, tuần trước…; hiện lịch ra như thanh ngang mà bấm
 * cũng tiện").
 *
 * Ba tầng, cùng trả về MỘT khoảng `{tu, den}` (yyyy-mm-dd, giờ VN) hoặc null =
 * tất cả:
 *   1. chip bấm nhanh: Hôm nay · Hôm qua · Hôm kia · 7 ngày · Tuần trước ·
 *      30 ngày · Tất cả;
 *   2. dải ngày ngang (cuộn ngang trong thanh, trang không cuộn) — bấm một ngày
 *      là xem đúng ngày ấy;
 *   3. "Tuỳ chọn": hai ô ngày từ → đến.
 *
 * Chỉ vẽ + tính khoảng (lib/thanh-ngay.ts, hàm thuần có test). Màn tự đưa khoảng
 * xuống máy chủ (`tu`/`den`); máy chủ là nơi quyết khoảng hợp lệ.
 *
 * `motNgay` (29/09/2026 — `/doi-tac`, phòng dịch vụ): chọn ĐÚNG MỘT ngày. Chỉ
 * còn chip Hôm nay · Hôm qua · Hôm kia, dải ngày và "Chọn ngày…" (một ô ngày);
 * không "Tất cả", không khoảng. Vẫn trả `{tu, den}` với tu = den.
 */

import { useState } from "react";

import Button from "@/components/ui/Button";
import {
  NHANH,
  daiNgay,
  docKhoang,
  khoangNhanh,
  maCuaKhoang,
  nhanKhoang,
  type Khoang,
} from "@/lib/thanh-ngay";

const CHIP =
  "inline-flex min-h-10 shrink-0 items-center rounded-control px-3 text-body font-medium transition-colors duration-100 md:min-h-8";
const CHIP_CHON = "bg-brand-600 text-white";
const CHIP_THUONG = "bg-surface-muted text-ink-soft hover:bg-surface-sunken";

export default function ThanhNgay({
  khoang,
  homNay,
  onChon,
  nhan = "Khoảng ngày",
  soNgayTruoc = 13,
  soNgaySau = 7,
  dangTai = false,
  className = "",
  motNgay: chiMotNgay = false,
}: {
  /** Khoảng đang lọc; null = tất cả. */
  khoang: Khoang | null;
  /** Hôm nay theo giờ VN (yyyy-mm-dd) — màn truyền vào để thuần và test được. */
  homNay: string;
  onChon: (k: Khoang | null) => void;
  /** aria-label của cả thanh. */
  nhan?: string;
  /** Dải ngày: bao nhiêu ngày trước / sau hôm nay. */
  soNgayTruoc?: number;
  soNgaySau?: number;
  dangTai?: boolean;
  className?: string;
  /** Chọn đúng một ngày (không khoảng, không "Tất cả"). */
  motNgay?: boolean;
}) {
  const [moTuyChon, setMoTuyChon] = useState(false);
  const [tu, setTu] = useState(khoang?.tu ?? "");
  const [den, setDen] = useState(khoang?.den ?? "");
  const maDang = maCuaKhoang(khoang, homNay);
  const motNgay = khoang && khoang.tu === khoang.den ? khoang.tu : null;
  const tuyChon = khoang !== null && maDang === null && motNgay === null;
  const kTuyChon = chiMotNgay ? docKhoang(tu, tu) : docKhoang(tu, den);
  const dai = daiNgay(homNay, soNgayTruoc, soNgaySau);
  // Chế độ một ngày: ngày đang chọn nằm ngoài dải và không khớp chip nào →
  // nút "Chọn ngày…" mang tên ngày ấy (để người xem biết đang xem ngày nào).
  const ngayNgoaiDai =
    chiMotNgay && motNgay !== null && maDang === null && !dai.some((o) => o.ngay === motNgay);
  const chipNhanh = chiMotNgay
    ? NHANH.filter(({ ma }) => {
        const k = khoangNhanh(ma, homNay);
        return k !== null && k.tu === k.den;
      })
    : NHANH;

  return (
    <div role="group" aria-label={nhan} className={`min-w-0 space-y-2 ${className}`}>
      <div className="flex min-w-0 flex-wrap items-center gap-1">
        {chipNhanh.map(({ ma, nhan: ten }) => (
          <button
            key={ma}
            type="button"
            aria-pressed={maDang === ma}
            onClick={() => onChon(khoangNhanh(ma, homNay))}
            className={`${CHIP} ${maDang === ma ? CHIP_CHON : CHIP_THUONG}`}
          >
            {ten}
          </button>
        ))}
        {chiMotNgay ? null : (
          <button
            type="button"
            aria-pressed={khoang === null}
            onClick={() => onChon(null)}
            className={`${CHIP} ${khoang === null ? CHIP_CHON : CHIP_THUONG}`}
          >
            Tất cả
          </button>
        )}
        <button
          type="button"
          aria-expanded={moTuyChon}
          aria-pressed={tuyChon || ngayNgoaiDai}
          onClick={() => setMoTuyChon((v) => !v)}
          className={`${CHIP} ${tuyChon || ngayNgoaiDai ? CHIP_CHON : CHIP_THUONG}`}
        >
          {chiMotNgay
            ? ngayNgoaiDai
              ? `Ngày ${nhanKhoang(khoang)}`
              : "Chọn ngày…"
            : tuyChon
              ? `Tuỳ chọn: ${nhanKhoang(khoang)}`
              : "Tuỳ chọn…"}
        </button>
        {dangTai ? <span className="text-meta text-ink-muted">đang tải…</span> : null}
      </div>

      {moTuyChon ? (
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-meta text-ink-muted">
            {chiMotNgay ? "Ngày" : "Từ ngày"}
            <input
              type="date"
              value={tu}
              max={chiMotNgay ? homNay : undefined}
              onChange={(e) => setTu(e.target.value)}
              className="min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink"
            />
          </label>
          {chiMotNgay ? null : (
            <label className="flex flex-col gap-1 text-meta text-ink-muted">
              Đến ngày
              <input
                type="date"
                value={den}
                onChange={(e) => setDen(e.target.value)}
                className="min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink"
              />
            </label>
          )}
          <Button
            size="lg"
            variant="primary"
            disabled={kTuyChon === null}
            onClick={() => {
              onChon(kTuyChon);
              setMoTuyChon(false);
            }}
          >
            {chiMotNgay ? "Xem ngày này" : "Xem khoảng này"}
          </Button>
        </div>
      ) : null}

      {/* DẢI NGÀY: cuộn ngang TRONG thanh — thân trang không cuộn ngang
          (DESIGN.md §7). */}
      <div className="-mx-1 overflow-x-auto overscroll-x-contain px-1 pb-1">
        <div className="flex w-max gap-1">
          {dai.map((o) => {
            const dang = motNgay === o.ngay;
            return (
              <button
                key={o.ngay}
                type="button"
                aria-pressed={dang}
                aria-label={`${o.thu} ${o.so}${o.homNay ? " (hôm nay)" : ""}`}
                onClick={() => onChon({ tu: o.ngay, den: o.ngay })}
                className={`flex min-h-10 w-12 shrink-0 flex-col items-center justify-center rounded-control text-meta tabular-nums transition-colors duration-100 ${
                  dang
                    ? CHIP_CHON
                    : o.homNay
                      ? "bg-brand-50 font-semibold text-brand-700 hover:bg-brand-100"
                      : CHIP_THUONG
                }`}
              >
                <span className="font-medium">{o.thu}</span>
                <span>{o.so}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
