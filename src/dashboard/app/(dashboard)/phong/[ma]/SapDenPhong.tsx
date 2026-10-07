"use client";

// KHỐI "SẮP ĐẾN" — dây Nhận khách tại phòng (Tuyền chốt 07/10/2026,
// docs/KE-HOACH-NHAN-TAI-PHONG.md). Danh sách THEO KHÁCH do máy chủ trả
// (`sap_den_phong` của hàng chờ phòng): MỌI khách có chỉ định chưa vào phòng
// nào mà phòng này làm được — kể cả khách chưa chốt ở quầy, KHÔNG ẩn theo phòng
// chuyên ("ngu ngu tí nhưng pick ra dễ"). Khách có chỉ định tick sẵn (hướng
// dẫn tới đây / phòng chuyên ★) đứng đầu (máy chủ xếp).
//
// MỖI KHÁCH MỘT Ô: trong ô các chỉ định phòng làm được + trạng thái. Bấm
// [Nhận…] mở danh sách tick (`NhanChiDinh`) — nhận theo TỪNG CHỈ ĐỊNH.

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { type ThongBao } from "@/components/ui/ThongBaoHoanTac";

import { cauChiDinhPhong, type ChiDinhPhong, type DangOPhong } from "../../_lam-viec/api";
import ChonBacSiLam, { coChonBacSi, type LuaChonBacSi } from "../../_lam-viec/ChonBacSiLam";
import NhanChiDinh from "./NhanChiDinh";

/** "đang chờ / đang làm ở <phòng>" — giữ nguyên chữ hoa của tên phòng. */
function cauKhachDangO(d: DangOPhong): string {
  return `đang ${d.trang_thai === "lam" ? "làm" : "chờ"} ở ${d.phong ?? "phòng khác"}`;
}

export interface KhachSapDen {
  visit_id: string;
  khach: string | null;
  ma_khach: string | null;
  duoc_huong_dan: boolean;
  co_tick_san: boolean;
  so_chi_dinh: number;
  dang_o_phong: DangOPhong | null;
  chi_dinh: ChiDinhPhong[];
}

export default function SapDenPhong({
  roomId,
  ds,
  bacSi,
  onDaNhan,
  onBao,
}: {
  roomId: string;
  ds: KhachSapDen[];
  /** Bác sĩ trực của phòng — chỉ có phần tử khi ≥2 bác sĩ (máy chủ quyết). */
  bacSi: LuaChonBacSi[];
  onDaNhan: () => void;
  onBao: (tb: ThongBao) => void;
}) {
  const [mo, setMo] = useState<string | null>(null);
  const [chonBs, setChonBs] = useState("");

  if (ds.length === 0) return null;

  return (
    <section aria-label="Khách sắp đến phòng" className="space-y-2 rounded-card border border-info bg-info-bg p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-meta font-semibold uppercase tracking-wide text-info">Sắp đến ({ds.length})</p>
        {coChonBacSi(bacSi) ? (
          <ChonBacSiLam co="nho" ds={bacSi} value={chonBs} disabled={mo !== null} onChon={setChonBs} />
        ) : null}
      </div>
      <ul className="space-y-2">
        {ds.map((k) => (
          <li key={k.visit_id} className="space-y-1 rounded-control bg-surface p-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="min-w-0 flex-1 text-body text-ink">
                <span className="font-semibold">{k.khach ?? "—"}</span>
                {k.ma_khach ? <span className="text-ink-muted"> · {k.ma_khach}</span> : null}
                <span className="text-meta text-ink-muted"> · {k.so_chi_dinh} chỉ định</span>
              </span>
              {mo !== k.visit_id ? (
                <Button type="button" size="sm" variant="primary" onClick={() => setMo(k.visit_id)}>
                  Nhận…
                </Button>
              ) : null}
            </div>
            <ul className="space-y-0.5 text-meta">
              {k.chi_dinh.map((c) => (
                <li key={c.id} className="flex flex-wrap items-baseline gap-x-1.5">
                  <span className="text-ink">
                    {c.ten ?? "—"}
                    {c.chuyen ? " ★" : ""}
                  </span>
                  <span className={c.trang_thai === "sap_den" ? "text-ink-muted" : "text-warning"}>
                    {cauChiDinhPhong(c)}
                    {c.chua_chot ? " · chưa chốt" : ""}
                  </span>
                </li>
              ))}
            </ul>
            {k.duoc_huong_dan || k.dang_o_phong ? (
              <div className="flex flex-wrap gap-1">
                {k.duoc_huong_dan ? <Chip tone="info">Được hướng dẫn đến đây</Chip> : null}
                {k.dang_o_phong ? <Chip tone="warning">Khách {cauKhachDangO(k.dang_o_phong)}</Chip> : null}
              </div>
            ) : null}
            {mo === k.visit_id ? (
              <NhanChiDinh
                roomId={roomId}
                visitId={k.visit_id}
                khach={k.khach}
                chiDinh={k.chi_dinh}
                bacSiLamId={chonBs}
                onThoi={() => setMo(null)}
                onBao={onBao}
                onXong={() => {
                  setMo(null);
                  onDaNhan();
                }}
              />
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
