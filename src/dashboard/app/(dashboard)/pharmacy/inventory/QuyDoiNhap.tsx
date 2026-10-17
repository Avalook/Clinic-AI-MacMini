"use client";

// Quy đổi đơn vị lúc nhập (17/10/2026): thuốc bán theo "viên" mà nhập theo "hộp"
// thì kho PHẢI ghi theo viên — nếu không giao thuốc ghi tiền mà không trừ được kho.
// Máy chủ quyết có phải đổi không, hệ số nào, kết quả bao nhiêu, hệ số lạ hay
// không (`GET /api/pharmacy/quy-doi`); ở đây chỉ hỏi máy chủ và vẽ câu trả lời.
// Ô hệ số chỉ hiện khi đơn vị nhập khác đơn vị bán; đã nhớ hệ số thì khỏi gõ.

import { useEffect, useState } from "react";

import { INPUT, LABEL } from "../../form-ui";
import { docKho, soKho } from "./gui-kho";

interface XemQuyDoi {
  can_doi: boolean;
  don_vi_ban: string | null;
  he_so_da_nho: number | string | null;
  he_so: number | string | null;
  can_xac_nhan: boolean;
  so_luong_quy_doi: number | string | null;
}

export default function QuyDoiNhap({
  idThuoc,
  donVi,
  soLuong,
  heSo,
  xacNhan,
  onHeSo,
  onXacNhan,
  ma,
}: {
  idThuoc: string | null | undefined;
  donVi: string;
  soLuong: string;
  heSo: string;
  xacNhan: boolean;
  onHeSo: (v: string) => void;
  onXacNhan: (v: boolean) => void;
  /** Hậu tố id ô nhập (nhiều dòng phiếu cùng hiện). */
  ma: string;
}) {
  const [xem, setXem] = useState<XemQuyDoi | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  // Đổi thuốc hoặc đơn vị → hệ số gõ dở thuộc về đơn vị cũ, bỏ đi.
  useEffect(() => {
    onHeSo("");
    onXacNhan(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idThuoc, donVi]);

  useEffect(() => {
    if (!idThuoc || !donVi.trim()) return;
    let huy = false;
    const hen = setTimeout(async () => {
      const kq = await docKho<XemQuyDoi>("quy-doi", {
        drug_catalog_id: idThuoc,
        unit: donVi.trim(),
        he_so: heSo.trim(),
        so_luong: soLuong.trim(),
      });
      if (huy) return;
      if (kq.ok) {
        setXem(kq.data);
        setLoi(null);
      } else {
        setLoi(kq.loi);
      }
    }, 300);
    return () => {
      huy = true;
      clearTimeout(hen);
    };
  }, [idThuoc, donVi, heSo, soLuong]);

  // Chưa chọn thuốc / đơn vị: kết quả cũ (của thuốc trước) không được hiện.
  const coDauVao = Boolean(idThuoc) && donVi.trim() !== "";
  if (!coDauVao || (!xem?.can_doi && !loi)) return null;
  const ban = xem?.don_vi_ban ?? "";
  const nho = xem?.he_so_da_nho;

  return (
    <div
      role="status"
      className="space-y-2 rounded-control border border-line bg-surface p-3 text-body text-ink-soft"
    >
      <p>
        Thuốc này bán theo “{ban}”, bạn nhập theo “{donVi.trim()}” — kho chỉ giữ “{ban}”, nên
        phải đổi.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <label className="block">
          <span className={LABEL}>
            1 {donVi.trim()} = ? {ban}
          </span>
          <input
            id={`qd-he-so-${ma}`}
            value={heSo}
            inputMode="decimal"
            placeholder={nho != null ? soKho(nho) : "vd 10"}
            onChange={(e) => {
              onHeSo(e.target.value);
              onXacNhan(false);
            }}
            className={`${INPUT} w-32`}
          />
        </label>
        {xem?.so_luong_quy_doi != null ? (
          <p className="pb-2 font-semibold text-ink tabular-nums">
            = {soKho(xem.so_luong_quy_doi)} {ban}
          </p>
        ) : null}
        {nho != null && heSo.trim() === "" ? (
          <p className="pb-2 text-meta text-ink-muted">
            Đã nhớ lần trước: 1 {donVi.trim()} = {soKho(nho)} {ban}.
          </p>
        ) : null}
      </div>
      {xem?.can_xac_nhan ? (
        <label className="flex items-center gap-2 text-warning">
          <input
            type="checkbox"
            checked={xacNhan}
            onChange={(e) => onXacNhan(e.target.checked)}
          />
          Hệ số này lệch hơn 10 lần so với lần trước — đúng, hệ số này.
        </label>
      ) : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
