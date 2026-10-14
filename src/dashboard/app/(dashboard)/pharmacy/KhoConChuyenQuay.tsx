"use client";

// "Kho còn N — chuyển sang quầy?" (G7, 14/10/2026). Cơ sở tách kho / quầy: quầy
// hết lô cho thuốc đang bán mà kho còn → một nút lập phiếu chuyển ngay tại màn
// bán (luật open: người làm được thì hệ cho làm, phiếu ghi ai/lúc/lý do và hoàn
// tác được ở Kho thuốc → Chuyển kho). Luật chuyển (quá tồn, lô hết hạn, số rác)
// ở máy chủ; câu từ chối hiện nguyên văn.

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import Button from "@/components/ui/Button";
import { INPUT } from "../form-ui";
import { fmtNgay, fmtSo, type LoKhoCon } from "./ban-thuoc";
import { guiKho } from "./inventory/gui-kho";

export default function KhoConChuyenQuay({
  khoCon,
  can,
  tenThuoc,
  chiXem = false,
}: {
  khoCon: LoKhoCon[];
  /** Số còn cần cho dòng đơn — điền sẵn ô số lượng (máy chủ vẫn chặn quá tồn kho). */
  can: number;
  tenThuoc: string;
  /** Người xem không ghi được — chỉ hiện thông tin, không có nút. */
  chiXem?: boolean;
}) {
  const router = useRouter();
  const [lo, setLo] = useState(khoCon[0]?.drug_batch_id ?? "");
  const chon = khoCon.find((b) => b.drug_batch_id === lo) ?? khoCon[0];
  const [so, setSo] = useState(can > 0 ? String(Math.min(can, chon?.ton ?? can)) : "");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const khoa = useRef(crypto.randomUUID());

  if (!chon) return null;
  const tong = khoCon.reduce((s, b) => s + b.ton, 0);

  const chuyen = async () => {
    setDang(true);
    setLoi(null);
    const kq = await guiKho(
      "chuyen-kho",
      {
        huong: "KHO_QUAY",
        ly_do: `Chuyển sang quầy để bán: ${tenThuoc}`,
        dong: [{ drug_batch_id: chon.drug_batch_id, so_luong: so.trim() }],
      },
      khoa.current,
    );
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    khoa.current = crypto.randomUUID();
    router.refresh();
  };

  return (
    <div className="space-y-2 rounded-control bg-surface-muted px-3 py-2">
      <p className="text-meta text-ink">
        Quầy hết lô cho thuốc này, nhưng <span className="font-medium">kho còn {fmtSo(tong)} {chon.unit}</span> —
        chuyển sang quầy?
      </p>
      {chiXem ? null : (
        <div className="flex flex-wrap items-end gap-2">
          <label className="block flex-1 text-xs text-ink-muted">
            Lô ở kho
            <select value={chon.drug_batch_id} onChange={(e) => setLo(e.target.value)} className={`${INPUT} mt-1`}>
              {khoCon.map((b) => (
                <option key={b.drug_batch_id} value={b.drug_batch_id}>
                  {b.batch_code} · HSD {fmtNgay(b.expiry_date)} · kho còn {fmtSo(b.ton)} {b.unit}
                </option>
              ))}
            </select>
          </label>
          <label className="block w-28 text-xs text-ink-muted">
            Số chuyển
            <input
              type="number"
              min="0"
              step="any"
              value={so}
              onChange={(e) => setSo(e.target.value)}
              className={`${INPUT} mt-1`}
            />
          </label>
          <Button
            type="button"
            variant="primary"
            className="max-sm:h-10 max-sm:px-4"
            disabled={dang || !so.trim()}
            onClick={() => void chuyen()}
          >
            {dang ? "Đang chuyển…" : "Chuyển sang quầy"}
          </Button>
        </div>
      )}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
