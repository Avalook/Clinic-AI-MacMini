"use client";

// Tab TIÊU HAO của Kho vật tư (G8a, 14/10/2026): phòng × kỳ (tuần / tháng / tự chọn)
// + giá trị theo giá nhập đã chốt trên sổ. Máy chủ tính hết (`GET /api/v1/vat-tu-kho/
// tieu-hao`): đầu / cuối = SỐ ĐẾM THẬT, nhận / trả giữa hai lần đếm, thiếu đếm thì
// nói "chưa đủ dữ liệu" chứ không suy từ tồn sổ. Màn chỉ chọn kỳ và vẽ — không công
// thức nào trong TSX. Dòng dưới mức / cần kiểm đếm chỉ là chip trung tính.

import { useCallback, useEffect, useState } from "react";

import Chip from "@/components/ui/Chip";
import ChipLoc from "@/components/ui/ChipLoc";
import ONhap from "@/components/ui/ONhap";
import { useNgheBang } from "../dung-nghe-bang";
import { soVatTu, tienVatTu } from "./gui-vat-tu";

interface DongTieuHao {
  vat_tu_id: string;
  room_id: string;
  ten: string;
  don_vi: string | null;
  phong: string;
  du_du_lieu: boolean;
  ly_do_thieu: string;
  dau: number | null;
  nhan: number | null;
  tra: number | null;
  cuoi: number | null;
  tieu_hao: number | null;
  trong_do_huy: number | null;
  gia_nhap: number;
  gia_tri: number | null;
  dem_dau_luc: string | null;
  dem_cuoi_luc: string | null;
  canh_bao: string;
}

interface GoiTieuHao {
  tu: string;
  den: string;
  items: DongTieuHao[];
  theo_phong: { room_id: string; phong: string; gia_tri: number; so_dong: number; chua_du: number }[];
  tong_gia_tri: number;
}

type Ky = "tuan" | "thang" | "tuy";

const ngay = (iso: string) => iso.split("-").reverse().join("/");
const gio = (iso: string | null) =>
  iso
    ? new Date(iso).toLocaleString("vi-VN", {
        timeZone: "Asia/Ho_Chi_Minh",
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";

export default function TieuHaoVatTu() {
  const [ky, setKy] = useState<Ky>("tuan");
  const [tu, setTu] = useState("");
  const [den, setDen] = useState("");
  const [chiDu, setChiDu] = useState(false);
  const [goi, setGoi] = useState<GoiTieuHao | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  const tai = useCallback(async () => {
    const q = new URLSearchParams({ ky });
    if (ky === "tuy") {
      q.set("tu", tu);
      q.set("den", den);
    }
    try {
      const r = await fetch(`/api/vat-tu-kho/tieu-hao?${q}`, { cache: "no-store" });
      const d = (await r.json().catch(() => null)) as (GoiTieuHao & { error?: string }) | null;
      if (!r.ok || !d?.items) {
        setLoi(d?.error ?? "Không đọc được báo cáo tiêu hao.");
        return;
      }
      setLoi(null);
      setGoi(d);
    } catch {
      setLoi("Mất kết nối — chưa đọc được báo cáo tiêu hao.");
    }
  }, [ky, tu, den]);

  useEffect(() => {
    void tai();
  }, [tai]);
  // Phiếu mới / hoàn tác ở tab khác → báo cáo cập nhật ngay.
  useNgheBang(["vat_tu_txn"], () => void tai());

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <ChipLoc
          nhan="Kỳ báo cáo"
          chon={ky}
          onChon={setKy}
          muc={[
            { ma: "tuan", nhan: "Tuần này" },
            { ma: "thang", nhan: "Tháng này" },
            { ma: "tuy", nhan: "Tự chọn" },
          ]}
        />
        {ky === "tuy" ? (
          <>
            <ONhap type="date" aria-label="Từ ngày" value={tu} onChange={(e) => setTu(e.target.value)} />
            <ONhap type="date" aria-label="Đến ngày" value={den} onChange={(e) => setDen(e.target.value)} />
          </>
        ) : null}
        <ChipLoc
          nhan="Lọc dòng"
          chon={chiDu ? "du" : "tat_ca"}
          onChon={(v) => setChiDu(v === "du")}
          muc={[
            { ma: "tat_ca", nhan: "Tất cả dòng" },
            { ma: "du", nhan: "Chỉ dòng đủ dữ liệu" },
          ]}
        />
      </div>
      {goi ? (
        <p className="text-body text-ink-muted">
          Kỳ {ngay(goi.tu)} – {ngay(goi.den)} · Giá trị tiêu hao{" "}
          <span className="font-semibold tabular-nums text-ink">{tienVatTu(goi.tong_gia_tri)}</span>. Số liệu
          tính từ hai lần kiểm đếm gần nhất của từng phòng; phòng chưa đếm đủ hai lần thì chưa có số.
        </p>
      ) : null}
      {loi ? (
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
      ) : null}
      {goi && goi.theo_phong.length === 0 ? (
        <p className="rounded-card border border-line bg-surface px-4 py-6 text-center text-body text-ink-muted">
          Chưa có sổ vật tư ở phòng nào. Xuất kho cho phòng và kiểm đếm ở tab Phiếu để có báo cáo.
        </p>
      ) : null}
      {goi?.theo_phong.map((p) => {
        const dong = goi.items.filter((d) => d.room_id === p.room_id && (!chiDu || d.du_du_lieu));
        if (dong.length === 0) return null;
        return (
          <section key={p.room_id} aria-label={p.phong} className="space-y-1">
            <h3 className="flex flex-wrap items-baseline gap-x-3 text-title text-ink">
              {p.phong}
              <span className="text-body font-normal tabular-nums text-ink-muted">
                {tienVatTu(p.gia_tri)}
                {p.chua_du > 0 ? ` · ${p.chua_du} dòng chưa đủ dữ liệu` : ""}
              </span>
            </h3>
            <ul className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
              {dong.map((d) => (
                <li
                  key={`${d.room_id}-${d.vat_tu_id}`}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-hairline px-3 py-2 last:border-b-0"
                >
                  <div className="min-w-0 flex-1 basis-56">
                    <p className="text-emph font-medium text-ink">
                      {d.ten}
                      {d.canh_bao ? (
                        <Chip tone="neutral" className="ml-2">
                          {d.canh_bao.charAt(0).toUpperCase() + d.canh_bao.slice(1)}
                        </Chip>
                      ) : null}
                    </p>
                    <p className="text-meta text-ink-muted">
                      {d.du_du_lieu
                        ? `Đầu ${soVatTu(d.dau)} · Nhận ${soVatTu(d.nhan)} · Trả ${soVatTu(d.tra)} · Cuối ${soVatTu(d.cuoi)} (đếm ${gio(d.dem_dau_luc)} → ${gio(d.dem_cuoi_luc)})`
                        : d.ly_do_thieu}
                    </p>
                  </div>
                  {d.du_du_lieu ? (
                    <div className="text-right">
                      <p className="text-emph font-semibold tabular-nums text-ink">
                        {soVatTu(d.tieu_hao)} {d.don_vi ?? ""}
                      </p>
                      <p className="text-meta tabular-nums text-ink-muted">
                        {tienVatTu(d.gia_tri)}
                        {d.trong_do_huy ? ` · trong đó huỷ ${soVatTu(d.trong_do_huy)}` : ""}
                      </p>
                    </div>
                  ) : (
                    <Chip tone="neutral">Chưa đủ dữ liệu</Chip>
                  )}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
