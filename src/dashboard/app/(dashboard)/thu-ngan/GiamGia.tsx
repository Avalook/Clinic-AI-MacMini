"use client";

// Giảm giá theo TỔNG hoá đơn — dùng chung quầy dịch vụ, quầy thuốc, bán lẻ.
// Người thu tiền chọn tiền HOẶC %, gõ lý do (chữ tự do, bắt buộc). Máy chủ mới
// là bên quyết: nó tính lại, làm tròn 1đ, chặn vượt phần giảm được. Số hiện ở đây
// chỉ để người thu xem trước — `giamDuoc` (phần được phép giảm, trừ liệu trình
// trả trước) cũng do máy chủ báo, không suy ra ở trình duyệt.

import { useEffect, useState } from "react";

export interface GiamGiaParams {
  discount_type: "AMOUNT" | "PERCENT";
  discount_value: number;
  discount_reason: string;
}

export interface GiamGiaResult {
  /** null = không giảm (chưa bật / chưa nhập / chưa hợp lệ). */
  params: GiamGiaParams | null;
  /** Tiền giảm xem trước. */
  tienGiam: number;
  /** Số phải thu xem trước = tổng gốc − giảm. */
  tongSauGiam: number;
  /** Vì sao chưa thu được (null = ổn hoặc không giảm) — chặn nút Thu. */
  loi: string | null;
}

export const KHONG_GIAM = (tong: number): GiamGiaResult => ({
  params: null,
  tienGiam: 0,
  tongSauGiam: tong,
  loi: null,
});

function tien(n: number): string {
  return n.toLocaleString("vi-VN") + "đ";
}

export default function GiamGia({
  tong,
  giamDuoc,
  onDoi,
}: {
  /** Tổng gốc hoá đơn (trước giảm). */
  tong: number;
  /** Phần của hoá đơn được phép giảm (máy chủ báo; thiếu = cả hoá đơn). */
  giamDuoc?: number;
  onDoi: (kq: GiamGiaResult) => void;
}) {
  const [batGiam, setBatGiam] = useState(false);
  const [loai, setLoai] = useState<"AMOUNT" | "PERCENT">("AMOUNT");
  const [giaTri, setGiaTri] = useState("");
  const [lyDo, setLyDo] = useState("");
  const tran = giamDuoc ?? tong;

  useEffect(() => {
    const ko = (loi: string | null, giam = 0): GiamGiaResult => ({
      params: null,
      tienGiam: giam,
      tongSauGiam: tong - giam,
      loi,
    });
    if (!batGiam || tong <= 0) return onDoi(KHONG_GIAM(tong));
    if (giaTri.trim() === "") return onDoi(KHONG_GIAM(tong)); // chưa nhập = thu nguyên giá
    const num = Number(giaTri);
    if (!Number.isFinite(num) || num <= 0) return onDoi(ko("Giá trị giảm phải lớn hơn 0."));
    if (loai === "PERCENT" && num > 100) return onDoi(ko("Phần trăm giảm phải từ 0 đến 100."));
    const giam = loai === "AMOUNT" ? Math.round(num) : Math.round((tran * num) / 100);
    if (giam <= 0) return onDoi(ko("Số tiền giảm làm tròn còn 0đ — nhập giá trị lớn hơn."));
    if (giam > tran) {
      return onDoi(
        ko(
          tran < tong
            ? `Giảm ${tien(giam)} vượt phần giảm được (${tien(tran)}) — liệu trình trả trước không giảm.`
            : `Giảm ${tien(giam)} vượt tổng hoá đơn ${tien(tran)}.`,
          giam,
        ),
      );
    }
    const reason = lyDo.trim();
    if (!reason) return onDoi(ko("Phải ghi lý do giảm giá.", giam));
    onDoi({
      params: { discount_type: loai, discount_value: num, discount_reason: reason },
      tienGiam: giam,
      tongSauGiam: tong - giam,
      loi: null,
    });
    // onDoi do cha truyền, đổi mỗi lần render — không đưa vào deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batGiam, loai, giaTri, lyDo, tong, tran]);

  if (tong <= 0 || tran <= 0) return null;

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

          <div className="flex flex-wrap items-center gap-2">
            <input
              type="number"
              inputMode="decimal"
              min={0}
              max={loai === "PERCENT" ? 100 : tran}
              step={loai === "PERCENT" ? 1 : 1000}
              value={giaTri}
              onChange={(e) => setGiaTri(e.target.value)}
              placeholder={loai === "AMOUNT" ? "Số tiền giảm" : "% giảm (0–100)"}
              aria-label={loai === "AMOUNT" ? "Số tiền giảm" : "Phần trăm giảm"}
              className="w-36 rounded-control border border-line bg-surface px-2 py-1 text-body tabular-nums text-ink"
            />
            {giaTri && Number.isFinite(Number(giaTri)) && Number(giaTri) > 0 ? (
              <span className="text-meta text-ink-muted">
                {loai === "AMOUNT"
                  ? `≈ ${((Number(giaTri) / tran) * 100).toFixed(1)}%`
                  : `≈ ${tien(Math.round((tran * Number(giaTri)) / 100))}`}
              </span>
            ) : null}
            {tran < tong ? (
              <span className="text-meta text-ink-muted">
                Giảm được tối đa {tien(tran)} (liệu trình trả trước không giảm)
              </span>
            ) : null}
          </div>

          <input
            type="text"
            value={lyDo}
            onChange={(e) => setLyDo(e.target.value)}
            placeholder="Lý do giảm giá (bắt buộc, VD: khách quen, người nhà bác sĩ)"
            aria-label="Lý do giảm giá"
            maxLength={500}
            className="w-full rounded-control border border-line bg-surface px-2 py-1 text-body text-ink"
          />
        </div>
      ) : null}
    </div>
  );
}
