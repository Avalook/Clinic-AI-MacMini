"use client";

// Ô đơn vị NHẬP kho (26/11/2026, PR C): chỉ CHỌN trong các đơn vị đã khai của thuốc
// (gốc + đơn vị khai thêm) — không gõ tự do. Đơn vị mới thì khai ở Danh mục trước.
// Danh sách và chữ hiển thị do máy chủ soạn (`GET /api/pharmacy/quy-doi`, trả
// `cac_don_vi`); ở đây chỉ vẽ. Thuốc chưa khai đơn vị gốc: giữ ô gõ cũ (ODonVi) —
// máy chủ không đổi gì cho thuốc ấy, câu nhắc khai nằm ở màn cha.

import { useEffect, useState } from "react";

import { INPUT } from "../../form-ui";
import ODonVi from "../../ODonVi";
import { docKho } from "./gui-kho";

interface DonViNhap {
  don_vi: string;
  he_so: string;
  goc: boolean;
  nhan: string;
}

const chuan = (s: string) => s.trim().toLocaleLowerCase("vi");

export default function ChonDonViNhap({
  idThuoc,
  value,
  onChange,
  ariaLabel = "Đơn vị nhập",
}: {
  idThuoc: string | null | undefined;
  value: string;
  onChange: (v: string) => void;
  ariaLabel?: string;
}) {
  // Kết quả gắn với id thuốc đã hỏi: đổi thuốc thì danh sách cũ tự thành "chưa có".
  const [kq, setKq] = useState<{ id: string; ds: DonViNhap[] | null; loi: string | null } | null>(
    null,
  );
  const ds = idThuoc && kq?.id === idThuoc ? kq.ds : null;
  const loi = idThuoc && kq?.id === idThuoc ? kq.loi : null;

  useEffect(() => {
    if (!idThuoc) return;
    let huy = false;
    void docKho<{ cac_don_vi: DonViNhap[] }>("quy-doi", { drug_catalog_id: idThuoc, unit: "" }).then(
      (r) => {
        if (huy) return;
        setKq(
          r.ok
            ? { id: idThuoc, ds: r.data.cac_don_vi ?? [], loi: null }
            : { id: idThuoc, ds: null, loi: r.loi },
        );
      },
    );
    return () => {
      huy = true;
    };
  }, [idThuoc]);

  // Chữ đang có (đơn vị lô cũ, quét tem) khớp một đơn vị đã khai → dùng đúng chữ ấy;
  // không khớp → để trống cho người nhập chọn lại, không ghi đơn vị lạ.
  useEffect(() => {
    if (!ds || ds.length === 0) return;
    const khop = ds.find((d) => chuan(d.don_vi) === chuan(value));
    const dung = khop?.don_vi ?? "";
    if (dung !== value) onChange(dung);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ds, value]);

  if (ds && ds.length === 0) {
    return <ODonVi value={value} onChange={onChange} ariaLabel={ariaLabel} />;
  }
  return (
    <>
      <select
        aria-label={ariaLabel}
        value={value}
        disabled={!idThuoc || !ds}
        onChange={(e) => onChange(e.target.value)}
        className={INPUT}
      >
        <option value="">{idThuoc ? "Chọn đơn vị…" : "Chọn thuốc trước"}</option>
        {(ds ?? []).map((d) => (
          <option key={d.don_vi} value={d.don_vi}>
            {d.nhan}
          </option>
        ))}
      </select>
      {loi ? (
        <span role="alert" className="mt-1 block text-meta text-danger">
          {loi}
        </span>
      ) : idThuoc && ds ? (
        <span className="mt-1 block text-meta text-ink-muted">
          Thiếu đơn vị? Khai ở Danh mục.
        </span>
      ) : null}
    </>
  );
}
