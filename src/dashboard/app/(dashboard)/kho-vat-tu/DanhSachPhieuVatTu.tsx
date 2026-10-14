"use client";

// Danh sách PHIẾU Kho vật tư (G8a, 14/10/2026): ai lập, lúc nào, lý do, từng dòng.
// Sổ chỉ thêm — KHÔNG có nút sửa / xoá; sai thì [Hoàn tác] = lập phiếu đảo (mỗi
// phiếu đảo được một lần). Phiếu huỷ hay phiếu đảo là việc bình thường → chip
// trung tính, không hộp vàng-đỏ.

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import NutHoanTac from "@/components/ui/NutHoanTac";
import { guiVatTu, soVatTu, tienVatTu } from "./gui-vat-tu";
import { KIEU_PHIEU } from "./LapPhieuVatTu";

interface DongPhieu {
  vat_tu_id: string;
  ten: string;
  don_vi: string | null;
  noi_chua: string;
  so_luong: number;
  thuc_te: number | null;
  gia_nhap: number;
}

export interface PhieuVatTu {
  id: string;
  ma_phieu: string;
  loai: string;
  tao_luc: string;
  ghi_chu: string | null;
  nguoi_tao: string | null;
  dao_phieu_id: string | null;
  da_dao: boolean;
  dong: DongPhieu[];
}

const gio = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

const tenLoai = (loai: string) => (loai === "HOAN" ? "Phiếu đảo (hoàn tác)" : (KIEU_PHIEU[loai]?.nhan ?? loai));

/** Một dòng sổ: số đếm (kiểm) hoặc số có dấu (+ vào / − ra) tại nơi chứa. */
function chuDong(d: DongPhieu): string {
  const dv = d.don_vi ? ` ${d.don_vi}` : "";
  if (d.thuc_te != null) return `đếm được ${soVatTu(d.thuc_te)}${dv} (sổ ${d.so_luong >= 0 ? "+" : ""}${soVatTu(d.so_luong)})`;
  return `${d.so_luong > 0 ? "+" : ""}${soVatTu(d.so_luong)}${dv}`;
}

export default function DanhSachPhieuVatTu({ ds }: { ds: PhieuVatTu[] }) {
  const router = useRouter();
  const [mo, setMo] = useState<string | null>(null);
  const maPhieu = new Map(ds.map((p) => [p.id, p.ma_phieu]));

  return (
    <section aria-label="Phiếu đã lập" className="space-y-2">
      <h3 className="text-title text-ink">Phiếu đã lập</h3>
      {ds.length === 0 ? (
        <p className="rounded-card border border-line bg-surface px-4 py-6 text-center text-body text-ink-muted">
          Chưa có phiếu nào.
        </p>
      ) : (
        <ul className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
          {ds.map((p) => {
            const dangMo = mo === p.id;
            const tong = p.dong.reduce((s, d) => s + Math.abs(Number(d.so_luong)) * Number(d.gia_nhap), 0);
            return (
              <li key={p.id} className="border-b border-hairline px-3 py-2 last:border-b-0">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                  <div className="min-w-0 flex-1 basis-56">
                    <p className="text-emph font-medium text-ink">
                      {p.ma_phieu} <Chip tone="neutral">{tenLoai(p.loai)}</Chip>
                      {p.da_dao ? <Chip tone="neutral" className="ml-1">Đã hoàn tác</Chip> : null}
                    </p>
                    <p className="text-meta text-ink-muted">
                      {gio(p.tao_luc)} · {p.nguoi_tao ?? "—"}
                      {p.dao_phieu_id ? ` · đảo phiếu ${maPhieu.get(p.dao_phieu_id) ?? ""}` : ""}
                      {p.ghi_chu ? ` · ${p.ghi_chu}` : ""}
                    </p>
                  </div>
                  <span className="text-meta tabular-nums text-ink-muted">
                    {p.dong.length} dòng
                    {p.loai === "NHAP" || p.loai === "HUY" ? ` · ${tienVatTu(tong)}` : ""}
                  </span>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setMo(dangMo ? null : p.id)}>
                    {dangMo ? "Thu gọn" : "Xem dòng"}
                  </Button>
                  {p.loai !== "HOAN" && !p.da_dao ? (
                    <NutHoanTac
                      tieuDe="Hoàn tác phiếu này?"
                      moTa="Lập phiếu đảo — tồn trở về như trước phiếu"
                      goi={async () => {
                        const kq = await guiVatTu("hoan", { phieu_id: p.id }, `hoan-${p.id}`);
                        return kq.ok ? { ok: true } : { ok: false, loi: kq.loi };
                      }}
                      onXong={() => router.refresh()}
                    />
                  ) : null}
                </div>
                {dangMo ? (
                  <ul className="mt-2 space-y-1 rounded-control bg-surface-muted px-3 py-2 text-meta text-ink">
                    {p.dong.map((d, i) => (
                      <li key={`${d.vat_tu_id}-${d.noi_chua}-${i}`}>
                        <span className="font-medium">{d.ten}</span> · {d.noi_chua} · {chuDong(d)}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
