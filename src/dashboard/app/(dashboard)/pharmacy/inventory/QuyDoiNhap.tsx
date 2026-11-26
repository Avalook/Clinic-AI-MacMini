"use client";

// Quy đổi lúc nhập: nhập theo hộp mà kho đếm theo viên thì kho ghi số viên. Từ
// 26/11/2026 (PR C) câu nói bằng lời người — "1 hộp có bao nhiêu viên?" và
// "47 hộp = 1.410 viên" — trước đây "1 hộp = ? hộp 30 viên" làm người nhập trả lời
// nhầm số viên. Mọi câu chữ, hệ số, kết quả do máy chủ soạn (`GET /api/pharmacy/
// quy-doi`); ở đây chỉ hỏi máy chủ và vẽ. Ô số điền sẵn hệ số đã khai ở Danh mục;
// gõ số khác khi hộp lần này khác.

import { useEffect, useState } from "react";

import { INPUT, LABEL } from "../../form-ui";
import { docKho, soKho } from "./gui-kho";

interface XemQuyDoi {
  can_doi: boolean;
  he_so_da_nho: number | string | null;
  can_xac_nhan: boolean;
  cau_hoi: string | null;
  ket_qua: string | null;
  loi: string | null;
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
        setLoi(kq.data.loi);
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
  const nho = xem?.he_so_da_nho;

  return (
    <div
      role="status"
      className="space-y-2 rounded-control border border-line bg-surface p-3 text-body text-ink-soft"
    >
      {!loi && xem?.cau_hoi ? (
        <div className="flex flex-wrap items-end gap-2">
          <label className="block">
            <span className={LABEL}>{xem.cau_hoi}</span>
            <input
              id={`qd-he-so-${ma}`}
              value={heSo}
              inputMode="decimal"
              placeholder={nho != null ? soKho(nho) : "vd 30"}
              onChange={(e) => {
                onHeSo(e.target.value);
                onXacNhan(false);
              }}
              className={`${INPUT} w-32`}
            />
          </label>
          {/* Máy chủ báo lỗi thì kết quả của lần xem TRƯỚC không được hiện cạnh câu báo. */}
          {xem.ket_qua ? (
            <p className="pb-2 font-semibold text-ink tabular-nums">{xem.ket_qua}</p>
          ) : null}
          {nho != null && heSo.trim() === "" ? (
            <p className="pb-2 text-meta text-ink-muted">
              Theo Danh mục: {soKho(nho)}. Lần này khác thì gõ số khác.
            </p>
          ) : null}
        </div>
      ) : null}
      {!loi && xem?.can_xac_nhan ? (
        <label className="flex items-center gap-2 text-warning">
          <input
            type="checkbox"
            checked={xacNhan}
            onChange={(e) => onXacNhan(e.target.checked)}
          />
          Số này lệch hơn 10 lần so với Danh mục — đúng, hệ số này.
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
