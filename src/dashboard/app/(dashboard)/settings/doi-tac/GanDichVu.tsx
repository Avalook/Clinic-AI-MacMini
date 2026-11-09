// (Client — chỉ `DoiTacView.tsx` dùng.) Các dịch vụ đã gán cho MỘT đối tác + form
// "Gán dịch vụ" (giá gợi ý, hẹn trả riêng, mã bên đối tác). Tách khỏi DoiTacView
// (trần 400 dòng, Gmail G4). Luật ô (giá, số ngày, mã chữ hoa) ở máy chủ `o_nhap`;
// màn chỉ gom ô và hiện câu lỗi.

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";

export interface DichVuGan {
  id: string;
  service_price_id: string;
  ten_dich_vu: string;
  unit_price: number | null;
  gia_goi_y: number | null;
  hen_tra_so_ngay: number | null;
  mac_dinh: boolean;
  /** Mã xét nghiệm phía đối tác (vd HPV) — Gmail G3 ghép theo mã trong tên tệp. */
  ma_ben_doi_tac: string | null;
  gia_hieu_luc: number | null;
  hen_tra_hieu_luc: number | null;
}

interface FormGan {
  service_price_id: string;
  gia_goi_y: string;
  hen_tra_so_ngay: string;
  ma_ben_doi_tac: string;
  /** Sửa dòng cũ giữ nguyên cờ nhận chỉ định mới (không giành của đối tác khác). */
  mac_dinh: boolean;
}

export const tien = (n: number | null) => (n ? `${n.toLocaleString("vi-VN")}đ` : "");

export default function GanDichVu({
  doiTacId,
  ganDuoc,
  henMacDinh,
  dichVu,
  dichVuThuHo,
  dang,
  gui,
}: {
  doiTacId: string;
  ganDuoc: boolean;
  henMacDinh: number | null;
  dichVu: DichVuGan[];
  dichVuThuHo: { id: string; name: string; unit_price: number | null }[];
  dang: boolean;
  gui: (method: "POST", duong: string, body: unknown, cau: string) => Promise<boolean>;
}) {
  const [gan, setGan] = useState<FormGan | null>(null);
  return (
    <>
      <ul className="divide-y divide-line rounded-card border border-line">
        {dichVu.map((g) => (
          <li key={g.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2">
            <span className="min-w-0 flex-1 text-body text-ink">
              {g.ten_dich_vu}
              {g.ma_ben_doi_tac ? <span className="text-meta text-ink-muted"> · mã {g.ma_ben_doi_tac}</span> : null}
            </span>
            <span className="text-meta tabular-nums text-ink-muted">
              {tien(g.gia_hieu_luc) || "Chưa có giá gợi ý"}
              {g.hen_tra_hieu_luc != null ? ` · hẹn ${g.hen_tra_hieu_luc} ngày` : " · chưa đặt hẹn"}
            </span>
            {g.mac_dinh ? null : <Chip tone="neutral">Không nhận chỉ định mới</Chip>}
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={dang}
              onClick={() =>
                setGan({
                  service_price_id: g.service_price_id,
                  gia_goi_y: g.gia_goi_y?.toString() ?? "",
                  hen_tra_so_ngay: g.hen_tra_so_ngay?.toString() ?? "",
                  ma_ben_doi_tac: g.ma_ben_doi_tac ?? "",
                  mac_dinh: g.mac_dinh,
                })
              }
            >
              Sửa
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={dang}
              onClick={() => void gui("POST", `doi-tac-dich-vu/${g.id}/bo`, {}, `Đã bỏ gán ${g.ten_dich_vu}.`)}
            >
              Bỏ gán
            </Button>
          </li>
        ))}
        {dichVu.length === 0 ? <li className="px-3 py-2 text-meta text-ink-muted">Chưa gán dịch vụ nào.</li> : null}
      </ul>

      {ganDuoc && !gan ? (
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() =>
            setGan({ service_price_id: "", gia_goi_y: "", hen_tra_so_ngay: "", ma_ben_doi_tac: "", mac_dinh: true })
          }
        >
          + Gán dịch vụ
        </Button>
      ) : null}
      {gan ? (
        <div className="grid gap-2 sm:grid-cols-5 sm:items-end">
          <label className="flex flex-col gap-1 text-meta text-ink-soft sm:col-span-2">
            Dịch vụ (đối tác thu)
            <OChon value={gan.service_price_id} onChange={(e) => setGan({ ...gan, service_price_id: e.target.value })}>
              <option value="">— Chọn dịch vụ —</option>
              {dichVuThuHo.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </OChon>
          </label>
          <label className="flex flex-col gap-1 text-meta text-ink-soft">
            Giá gợi ý
            <ONhap
              value={gan.gia_goi_y}
              inputMode="numeric"
              placeholder={tien(dichVuThuHo.find((s) => s.id === gan.service_price_id)?.unit_price ?? null)}
              onChange={(e) => setGan({ ...gan, gia_goi_y: e.target.value })}
            />
          </label>
          <label className="flex flex-col gap-1 text-meta text-ink-soft">
            Hẹn trả riêng (ngày)
            <ONhap
              value={gan.hen_tra_so_ngay}
              inputMode="numeric"
              maxLength={2}
              placeholder={henMacDinh?.toString() ?? ""}
              onChange={(e) => setGan({ ...gan, hen_tra_so_ngay: e.target.value })}
            />
          </label>
          <label className="flex flex-col gap-1 text-meta text-ink-soft">
            Mã bên đối tác
            <ONhap
              value={gan.ma_ben_doi_tac}
              maxLength={40}
              placeholder="vd HPV"
              onChange={(e) => setGan({ ...gan, ma_ben_doi_tac: e.target.value })}
            />
          </label>
          <p className="text-meta text-ink-muted sm:col-span-5">
            Gán xong, chỉ định MỚI của dịch vụ này đi đối tác này (đối tác cũ, nếu có, thôi nhận chỉ định mới). Mã
            bên đối tác: mã xét nghiệm đối tác ghi trong tên tệp kết quả (vd HPV) — để tự ghép đúng việc khi khách
            làm nhiều xét nghiệm cùng lúc.
          </p>
          <div className="flex flex-wrap gap-2 sm:col-span-5">
            <Button
              type="button"
              size="sm"
              variant="primary"
              disabled={dang || !gan.service_price_id}
              onClick={async () => {
                const ok = await gui("POST", "doi-tac-dich-vu", { doi_tac_id: doiTacId, ...gan }, "Đã gán dịch vụ.");
                if (ok) setGan(null);
              }}
            >
              Lưu
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setGan(null)}>
              Thôi
            </Button>
          </div>
        </div>
      ) : null}
    </>
  );
}
