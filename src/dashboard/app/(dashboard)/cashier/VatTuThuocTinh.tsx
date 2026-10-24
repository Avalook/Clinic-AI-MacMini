"use client";

import { useState } from "react";
import Button from "@/components/ui/Button";
import type { DongVatTu } from "./VatTuBangGia";

const CHU = [
  ["name", "Tên vật tư"],
  ["don_vi", "Đơn vị tính"], ["gia_nhap", "Giá nhập"], ["ma_vach", "Mã vạch"],
] as const;
const CO = [
  ["kinh_doanh", "Được kinh doanh"], ["can_ql_duyet", "Cần QL duyệt bán"],
  ["can_duyet_nhap", "Cần duyệt nhập"], ["chon_nhanh", "Chọn nhanh"],
] as const;
const O = "h-10 w-full rounded-control border border-line bg-surface px-2 text-body text-ink lg:h-8";

export default function VatTuThuocTinh({ d, ban, laQuanLy = false, onSua }: {
  d: DongVatTu; ban: boolean; laQuanLy?: boolean;
  onSua: (id: string, patch: Record<string, unknown>, xong: string) => Promise<boolean>;
}) {
  const [patch, setPatch] = useState<Record<string, string | boolean>>({});
  const doi = (key: string, value: string | boolean) => setPatch((p) => ({ ...p, [key]: value }));
  return (
    <details className="w-full basis-full text-body">
      <summary className="cursor-pointer py-2 text-brand-700">Sửa thuộc tính vật tư</summary>
      <div className="grid gap-3 py-3 sm:grid-cols-2 lg:grid-cols-4">
        {laQuanLy ? (
          <label className="space-y-1">
            <span>Loại vật tư</span>
            <select aria-label={`Loại vật tư ${d.name}`} disabled={ban} className={O}
              value={String(patch.loai_vat_tu ?? d.loai_vat_tu ?? "")}
              onChange={(e) => doi("loai_vat_tu", e.target.value)}>
              <option value="">Chưa phân loại</option>
              <option value="VPP">Văn phòng phẩm</option>
              <option value="VTYT">Vật tư y tế</option>
            </select>
          </label>
        ) : null}
        {CHU.map(([key, label]) => (
          <label key={key} className="space-y-1">
            <span>{label}</span>
            <input aria-label={`${label} ${d.name}`} disabled={ban} className={O}
              inputMode={key === "gia_nhap" ? "numeric" : "text"}
              value={String(patch[key] ?? d[key] ?? "")}
              onChange={(e) => doi(key, e.target.value)} />
          </label>
        ))}
        {CO.filter(([key]) => laQuanLy || key === "chon_nhanh").map(([key, label]) => (
          <label key={key} className="flex min-h-10 items-center gap-2">
            <input type="checkbox" aria-label={`${label} ${d.name}`} disabled={ban}
              checked={Boolean(patch[key] ?? d[key])} className="size-4 accent-brand-600"
              onChange={(e) => doi(key, e.target.checked)} />
            <span>{label}</span>
          </label>
        ))}
      </div>
      {laQuanLy ? (
        <p className="mb-2 text-meta text-ink-muted">Quản lý quyết định phân loại và mặt hàng cần duyệt.</p>
      ) : null}
      <Button type="button" size="sm" disabled={ban || Object.keys(patch).length === 0}
        onClick={async () => {
          if (await onSua(d.id, patch, `Đã lưu thuộc tính “${d.name}”.`)) setPatch({});
        }}>Lưu thuộc tính</Button>
    </details>
  );
}
