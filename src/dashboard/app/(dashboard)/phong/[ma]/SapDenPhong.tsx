"use client";

// KHỐI "SẮP ĐẾN" — dây Nhận khách tại phòng (Tuyền chốt 07/10/2026,
// docs/KE-HOACH-NHAN-TAI-PHONG.md). Danh sách THEO KHÁCH do máy chủ trả
// (`sap_den_phong` của hàng chờ phòng): mọi chỉ định chưa vào phòng nào mà phòng
// này làm được — kể cả khách chưa chốt ở quầy. Khách được hướng dẫn đến đây
// đứng đầu (máy chủ xếp).
//
// [Nhận vào phòng này] = lệnh `nhan-vao-phong` (máy chủ hỏi quyền, khoá lượt).
// Khách đang ở phòng khác → máy chủ trả 409 KHACH_O_PHONG_KHAC kèm tên phòng;
// màn hỏi MỘT câu xác nhận (không bắt lý do) rồi gửi lại `xac_nhan`. Nhận xong
// mời Hoàn tác vài giây (khách về Sắp đến).

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { type ThongBao } from "@/components/ui/ThongBaoHoanTac";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";

import { cauDangOPhong, guiThaoTac, type DangOPhong } from "../../_lam-viec/api";
import ChonBacSiLam, { coChonBacSi, type LuaChonBacSi } from "../../_lam-viec/ChonBacSiLam";
import { lenhHoanTac } from "../../_lam-viec/hoan-tac";

export interface KhachSapDen {
  visit_id: string;
  khach: string | null;
  ma_khach: string | null;
  duoc_huong_dan: boolean;
  dang_o_phong: DangOPhong | null;
  chi_dinh: { id: string; ten: string; chua_chot: boolean }[];
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
  const [dang, setDang] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [hoi, setHoi] = useState<{ visitId: string; cau: string } | null>(null);
  const [chonBs, setChonBs] = useState("");

  if (ds.length === 0) return null;

  const nhan = async (k: KhachSapDen, xacNhan: boolean) => {
    setDang(k.visit_id);
    setLoi(null);
    const kq = await guiThaoTac("nhan-vao-phong", k.visit_id, {
      room_id: roomId,
      ...(xacNhan ? { xac_nhan: true } : {}),
      ...(chonBs ? { bac_si_lam_id: chonBs } : {}),
    });
    setDang(null);
    if (!kq.ok) {
      if (kq.chiTiet?.ma === "KHACH_O_PHONG_KHAC") {
        setHoi({ visitId: k.visit_id, cau: kq.loi });
        return;
      }
      setHoi(null);
      setLoi(`${k.khach ?? "Khách"}: ${kq.loi}`);
      onDaNhan();
      return;
    }
    setHoi(null);
    const boQua = Array.isArray(kq.data.bo_qua) ? (kq.data.bo_qua as { ten: string; cau: string }[]) : [];
    if (boQua.length) setLoi(boQua.map((b) => `${b.ten}: ${b.cau}`).join(" · "));
    onBao({
      cau: `Đã nhận ${k.khach ?? "khách"} vào phòng`,
      goi: lenhHoanTac("hoan-tac-nhan", k.visit_id, { room_id: roomId }),
    });
    onDaNhan();
  };

  return (
    <section aria-label="Khách sắp đến phòng" className="space-y-2 rounded-card border border-info bg-info-bg p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-meta font-semibold uppercase tracking-wide text-info">Sắp đến ({ds.length})</p>
        {coChonBacSi(bacSi) ? (
          <ChonBacSiLam co="nho" ds={bacSi} value={chonBs} disabled={dang !== null} onChon={setChonBs} />
        ) : null}
      </div>
      <ul className="space-y-2">
        {ds.map((k) => (
          <li key={k.visit_id} className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="min-w-0 flex-1 text-body text-ink">
                <span className="font-semibold">{k.khach ?? "—"}</span>
                {k.ma_khach ? <span className="text-ink-muted"> · {k.ma_khach}</span> : null}
                <span className="block text-meta text-ink-muted">
                  {k.chi_dinh.map((c) => c.ten + (c.chua_chot ? " (chưa chốt)" : "")).join(" · ")}
                </span>
              </span>
              <Button
                type="button"
                size="sm"
                variant="primary"
                disabled={dang !== null}
                onClick={() => void nhan(k, false)}
              >
                {dang === k.visit_id ? "Đang nhận…" : "Nhận vào phòng này"}
              </Button>
            </div>
            {k.duoc_huong_dan || k.dang_o_phong ? (
              <div className="flex flex-wrap gap-1">
                {k.duoc_huong_dan ? <Chip tone="info">Được hướng dẫn đến đây</Chip> : null}
                {k.dang_o_phong ? <Chip tone="warning">{cauDangOPhong(k.dang_o_phong)}</Chip> : null}
              </div>
            ) : null}
            {hoi?.visitId === k.visit_id ? (
              <XacNhanTaiCho
                cau={hoi.cau}
                nhanDongY="Nhận sang phòng này"
                dangGui={dang !== null}
                onDongY={() => void nhan(k, true)}
                onThoi={() => setHoi(null)}
              />
            ) : null}
          </li>
        ))}
      </ul>
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </section>
  );
}
