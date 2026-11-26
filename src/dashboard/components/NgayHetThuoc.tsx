"use client";

// Ngày dự tính dùng hết thuốc của lượt — quầy thu thuốc và hoá đơn thuốc in (Tuyền 26/11).
// Máy chủ tính bằng đúng hàm của màn kê đơn (cách dùng danh mục × số lượng bán).
// `choIn`: hiện ô "In ngày dự tính uống hết thuốc lên hoá đơn" — bỏ tick thì khối này
// không ra giấy (vẫn thấy trên màn).

import { useEffect, useState } from "react";

import { goiThuoc } from "@/lib/goi-thuoc";

type Dong = { ten: string | null; so_luong: string; so_ngay: number; ngay_het: string };

export const ngayVn = (iso: string) => iso.slice(0, 10).split("-").reverse().join("/");

export type DongQuayHet = {
  id: string;
  drug_catalog_id: string | null;
  so_luong: string;
  don_vi: string;
  chu: string;
};

/** Quầy thu thuốc: {id dòng: "30 ngày → hết 22/12/2026"} theo số ĐANG BÁN của từng dòng.
 *  Hỏi lại khi quầy đổi số / đơn vị (chờ 400 ms sau lần gõ cuối). */
export function useNgayHetDong(visitId: string, dong: DongQuayHet[]): Record<string, string> {
  const [kq, setKq] = useState<{ goi: string; ds: Record<string, string> } | null>(null);
  const goi = JSON.stringify({ visit_id: visitId, dong: dong.filter((d) => d.drug_catalog_id && d.so_luong) });
  useEffect(() => {
    let bo = false;
    const t = setTimeout(() => {
      void goiThuoc<Record<string, { so_ngay: number; ngay_het: string }>>("het-thuoc-dong", {
        body: JSON.parse(goi) as unknown,
      }).then((r) => {
        if (bo || !r.ok) return;
        const ds = Object.fromEntries(
          Object.entries(r.data).map(([id, v]) => [id, `${v.so_ngay} ngày → hết ${ngayVn(v.ngay_het)}`]),
        );
        setKq({ goi, ds });
      });
    }, 400);
    return () => {
      bo = true;
      clearTimeout(t);
    };
  }, [goi]);
  return kq?.goi === goi ? kq.ds : {};
}

export default function NgayHetThuoc({
  visitId,
  phieuId,
  choIn = false,
}: {
  visitId?: string;
  phieuId?: string;
  choIn?: boolean;
}) {
  const [ds, setDs] = useState<Dong[]>([]);
  const [inRa, setInRa] = useState(false);

  useEffect(() => {
    let bo = false;
    const query: Record<string, string> = visitId ? { id: visitId } : { phieu: phieuId ?? "" };
    void goiThuoc<{ items: Dong[] }>("het-thuoc", { query }).then((r) => {
      if (!bo && r.ok) setDs(r.data.items);
    });
    return () => {
      bo = true;
    };
  }, [visitId, phieuId]);

  if (ds.length === 0) return null;
  return (
    <div className={`mt-3 text-meta ${choIn && !inRa ? "print:hidden" : ""}`}>
      {choIn ? (
        <label className="mb-1 flex items-center gap-2 text-ink print:hidden">
          <input type="checkbox" checked={inRa} onChange={(e) => setInRa(e.target.checked)} />
          In ngày dự tính uống hết thuốc lên hoá đơn
        </label>
      ) : null}
      <p className="font-semibold text-ink">Dự tính dùng hết thuốc</p>
      <ul>
        {ds.map((d, i) => (
          <li key={i} className="flex justify-between gap-2">
            <span>
              {d.ten ?? "Thuốc"} ({d.so_luong})
            </span>
            <span className="tabular-nums">
              {d.so_ngay} ngày → hết {ngayVn(d.ngay_het)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
