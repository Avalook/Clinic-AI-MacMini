"use client";

import { fmtSo, type LoKhoCon } from "./ban-thuoc";

/** Chỉ thông tin: bán/giao trước, đối chiếu nguồn và lô sau. */
export default function KhoConChuyenQuay({ khoCon }: {
  khoCon: LoKhoCon[];
  can: number;
  tenThuoc: string;
  chiXem?: boolean;
}) {
  const chon = khoCon[0];
  if (!chon) return null;
  const tong = khoCon.reduce((s, b) => s + b.ton, 0);
  return (
    <p className="rounded-control bg-surface-muted px-3 py-2 text-meta text-ink">
      Kho có {fmtSo(tong)} {chon.unit}. Có thể giao thuốc trước,
      xác nhận lô đã lấy tại Kho thuốc → Cần đối chiếu sau bán.
    </p>
  );
}
