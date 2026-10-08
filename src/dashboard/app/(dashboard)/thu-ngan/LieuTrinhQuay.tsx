"use client";

// Khối "LIỆU TRÌNH" của quầy thu dịch vụ (08/10/2026 — `docs/KE-HOACH-LIEU-TRINH.md`
// Q3: tiền liệu trình luôn thu ở quầy khi khách có mặt). Chỉ trong hoá đơn của
// khách ĐANG CHỌN — không thêm dòng nào ở danh sách chờ thu.
//
// Mỗi liệu trình một dòng: đã làm / đã trả / còn lại / tiền còn lại + ô [Trả
// trước … buổi] (1…tối đa) và [Trả hết] → thêm dòng "‹dịch vụ› — trả trước k
// buổi" vào hoá đơn đang thu (bấm lại = đổi số buổi), hoá đơn tải lại với
// revision mới. Bỏ dòng ấy bằng [Bỏ] ngay trên dòng hoá đơn (`HoaDonMot`).
// Mọi con số + tối đa do máy chủ tính (`LieuTrinhTienService.quay`).

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import ONhap from "@/components/ui/ONhap";
import { NHAN_TRANG_THAI_LT, docLT, lenhLT, tienLT, type LieuTrinhQuay as LTQ } from "@/lib/lieu-trinh";
import { useNgheBang } from "../dung-nghe-bang";

export default function LieuTrinhQuay({
  visitId,
  reloadToken,
  onDoi,
}: {
  visitId: string;
  /** Revision hoá đơn quầy — đổi thì đọc lại (vừa thu / vừa thêm dòng). */
  reloadToken?: string | null;
  /** Hoá đơn đổi → cha tải lại bảng quầy. */
  onDoi: () => void;
}) {
  const [ds, setDs] = useState<LTQ[] | null>(null);
  const nap = useCallback(() => {
    void docLT<{ lieu_trinh: LTQ[] }>("quay", visitId).then((d) => {
      if (d) setDs(d.lieu_trinh);
    });
  }, [visitId]);
  useEffect(() => {
    let huy = false;
    void docLT<{ lieu_trinh: LTQ[] }>("quay", visitId).then((d) => {
      if (!huy && d) setDs(d.lieu_trinh);
    });
    return () => {
      huy = true;
    };
  }, [visitId, reloadToken]);
  useNgheBang(["lieu_trinh", "lieu_trinh_buoi", "lieu_trinh_tra_truoc"], nap);

  if (!ds || ds.length === 0) return null;
  return (
    <div className="border-b border-line px-4 py-3">
      <p className="text-label font-semibold uppercase text-ink-muted">Liệu trình</p>
      <ul className="mt-1 divide-y divide-line">
        {ds.map((x) => (
          // Dòng đang chọn đổi (máy khác / vừa bỏ) → dựng lại ô số buổi.
          <DongLieuTrinh
            key={`${x.id}:${x.tra_truoc_dang_chon?.so_buoi ?? 0}`}
            x={x}
            visitId={visitId}
            onDoi={() => {
              nap();
              onDoi();
            }}
          />
        ))}
      </ul>
    </div>
  );
}

function DongLieuTrinh({ x, visitId, onDoi }: { x: LTQ; visitId: string; onDoi: () => void }) {
  const dangChon = x.tra_truoc_dang_chon;
  const [so, setSo] = useState(String(dangChon?.so_buoi ?? ""));
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const n = Number.parseInt(so, 10);

  const tra = async (soBuoi: number | "het") => {
    setDang(true);
    setLoi(null);
    const kq = await lenhLT("tra-truoc", {
      visit_id: visitId,
      lieu_trinh_id: x.id,
      so_buoi: soBuoi,
      expected_so_buoi: dangChon?.so_buoi ?? null,
    });
    setDang(false);
    if (!kq.ok) setLoi(kq.loi);
    onDoi();
  };

  return (
    <li className="space-y-1.5 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-body font-semibold text-ink">{x.service_name}</span>
        <Chip tone={x.trang_thai === "DUNG" ? "warning" : "info"}>{NHAN_TRANG_THAI_LT[x.trang_thai]}</Chip>
        <span className="text-meta text-ink-muted">{tienLT(x.don_gia)}/buổi</span>
      </div>
      <p className="text-meta tabular-nums text-ink-soft">
        Đã làm {x.da_lam}/{x.so_buoi} · đã trả {x.da_tra} · còn lại {x.con_lai} buổi
        {x.chua_tra > 0 ? ` · chưa trả ${x.chua_tra} buổi (${tienLT(x.tien_con_lai)})` : ""}
      </p>
      {dangChon ? (
        <p className="text-meta text-brand-700">
          Đang trong hoá đơn: trả trước {dangChon.so_buoi} buổi — bỏ bằng [Bỏ] ở dòng hoá đơn.
        </p>
      ) : null}
      {x.goi_y_tra_them ? (
        <p className="text-meta text-warning">Hết buổi đã trả trước — gợi ý khách trả thêm.</p>
      ) : null}
      {x.trang_thai === "DUNG" && x.hoan_duoc_toi_da > 0 ? (
        <p className="text-meta text-warning">
          Đã dừng, còn {x.hoan_duoc_toi_da} buổi đã trả chưa dùng — hoàn bằng [Hoàn tiền] ở tab “Đã thanh toán”.
        </p>
      ) : null}
      {x.tra_truoc_toi_da > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-meta text-ink-soft">
            Trả trước
            <ONhap
              type="number"
              inputMode="numeric"
              min={1}
              max={x.tra_truoc_toi_da}
              value={so}
              onChange={(e) => setSo(e.target.value)}
              aria-label={`Số buổi trả trước — ${x.service_name}`}
              className="w-20"
            />
            buổi (tối đa {x.tra_truoc_toi_da})
          </label>
          <Button
            size="sm"
            variant="soft"
            disabled={dang || !(n >= 1 && n <= x.tra_truoc_toi_da) || n === dangChon?.so_buoi}
            onClick={() => void tra(n)}
          >
            {dangChon ? "Đổi số buổi" : "Trả trước"}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={dang || dangChon?.so_buoi === x.tra_truoc_toi_da}
            onClick={() => void tra("het")}
          >
            Trả hết ({x.tra_truoc_toi_da} buổi)
          </Button>
        </div>
      ) : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </li>
  );
}
