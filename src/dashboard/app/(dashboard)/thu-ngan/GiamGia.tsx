"use client";

// Component giảm giá dùng chung cho quầy dịch vụ và quầy thuốc (13/10/2026).
//
// Hai hình thức: nhập tiền HOẶC % (radio). Khi nhập một ô, ô kia quy đổi tham
// khảo (read-only). Lý do bắt buộc (5–500 ký tự). Callback trả discount params
// để cha gửi lên API.

import { useEffect, useState } from "react";

export interface GiamGiaParams {
  discount_type: "AMOUNT" | "PERCENT";
  discount_value: number;
  discount_reason: string;
}

export interface GiamGiaResult {
  /** null = không giảm; GiamGiaParams = có giảm hợp lệ. */
  params: GiamGiaParams | null;
  /** Tiền giảm thực tế (tham khảo hiển thị). */
  tienGiam: number;
  /** Tổng sau giảm. */
  tongSauGiam: number;
  /** Lý do chưa hợp lệ (null = OK hoặc không bật giảm). */
  loi: string | null;
}

function tien(n: number): string {
  return n.toLocaleString("vi-VN") + "đ";
}

export default function GiamGia({
  tong,
  onDoi,
}: {
  /** Tổng gốc hoá đơn (trước giảm). */
  tong: number;
  /** Gọi mỗi khi thay đổi — cha dùng để cập nhật nút Thu. */
  onDoi: (kq: GiamGiaResult) => void;
}) {
  const [batGiam, setBatGiam] = useState(false);
  const [loai, setLoai] = useState<"AMOUNT" | "PERCENT">("AMOUNT");
  const [giaTri, setGiaTri] = useState("");
  const [lyDo, setLyDo] = useState("");

  useEffect(() => {
    if (!batGiam || tong <= 0) {
      onDoi({ params: null, tienGiam: 0, tongSauGiam: tong, loi: null });
      return;
    }
    const num = parseFloat(giaTri);
    if (Number.isNaN(num) || num < 0) {
      onDoi({ params: null, tienGiam: 0, tongSauGiam: tong, loi: "Giá trị không hợp lệ." });
      return;
    }
    let giam: number;
    if (loai === "AMOUNT") {
      giam = Math.round(num);
    } else {
      if (num > 100) {
        onDoi({ params: null, tienGiam: 0, tongSauGiam: tong, loi: "% giảm phải từ 0 đến 100." });
        return;
      }
      giam = Math.round((tong * num) / 100);
    }
    if (giam > tong) {
      onDoi({
        params: null,
        tienGiam: giam,
        tongSauGiam: tong - giam,
        loi: `Tiền giảm ${tien(giam)} vượt tổng hóa đơn ${tien(tong)}.`,
      });
      return;
    }
    const reason = lyDo.trim();
    if (giam > 0 && reason.length < 5) {
      onDoi({
        params: null,
        tienGiam: giam,
        tongSauGiam: tong - giam,
        loi: "Lý do giảm giá bắt buộc (ít nhất 5 ký tự).",
      });
      return;
    }
    onDoi({
      params: giam > 0 ? { discount_type: loai, discount_value: num, discount_reason: reason } : null,
      tienGiam: giam,
      tongSauGiam: tong - giam,
      loi: null,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batGiam, loai, giaTri, lyDo, tong]);

  if (tong <= 0) return null;

  return (
    <div className="space-y-2">
      <label className="flex items-center gap-2 text-body text-ink">
        <input
          type="checkbox"
          checked={batGiam}
          onChange={(e) => {
            setBatGiam(e.target.checked);
            if (!e.target.checked) {
              setGiaTri("");
              setLyDo("");
            }
          }}
          className="size-4 accent-brand-600"
        />
        Giảm giá / Miễn phí
      </label>

      {batGiam ? (
        <div className="space-y-2 rounded-control border border-line bg-surface-raised px-3 py-2">
          {/* Radio: loại giảm */}
          <div className="flex items-center gap-4 text-meta">
            <label className="flex items-center gap-1.5">
              <input
                type="radio"
                name="discount-type"
                checked={loai === "AMOUNT"}
                onChange={() => {
                  setLoai("AMOUNT");
                  setGiaTri("");
                }}
                className="accent-brand-600"
              />
              Giảm tiền (đ)
            </label>
            <label className="flex items-center gap-1.5">
              <input
                type="radio"
                name="discount-type"
                checked={loai === "PERCENT"}
                onChange={() => {
                  setLoai("PERCENT");
                  setGiaTri("");
                }}
                className="accent-brand-600"
              />
              Giảm %
            </label>
          </div>

          {/* Ô nhập + quy đổi */}
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="number"
              inputMode="decimal"
              min={0}
              max={loai === "PERCENT" ? 100 : tong}
              step={loai === "PERCENT" ? 1 : 1000}
              value={giaTri}
              onChange={(e) => setGiaTri(e.target.value)}
              placeholder={loai === "AMOUNT" ? "Số tiền giảm" : "% giảm (0–100)"}
              className="w-36 rounded-control border border-line bg-surface px-2 py-1 text-body tabular-nums text-ink"
            />
            {/* Quy đổi tham khảo */}
            {giaTri && !Number.isNaN(parseFloat(giaTri)) ? (
              <span className="text-meta text-ink-muted">
                {loai === "AMOUNT"
                  ? `≈ ${tong > 0 ? ((parseFloat(giaTri) / tong) * 100).toFixed(1) : 0}%`
                  : `≈ ${tien(Math.round((tong * parseFloat(giaTri)) / 100))}`}
              </span>
            ) : null}
          </div>

          {/* Lý do */}
          <input
            type="text"
            value={lyDo}
            onChange={(e) => setLyDo(e.target.value)}
            placeholder="Lý do giảm giá (bắt buộc, VD: khách quen, người nhà bác sĩ)"
            maxLength={500}
            className="w-full rounded-control border border-line bg-surface px-2 py-1 text-body text-ink"
          />
        </div>
      ) : null}
    </div>
  );
}
