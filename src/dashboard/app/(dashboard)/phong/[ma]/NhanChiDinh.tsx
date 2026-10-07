"use client";

// NHẬN THEO TỪNG CHỈ ĐỊNH (Tuyền chốt 07/10/2026 — lỗi staging: phòng thủ thuật
// "nhận theo khách" gom luôn hai chỉ định quầy hướng dẫn sang phòng siêu âm).
//
// Danh sách chỉ định phòng làm được, mỗi cái một ô tick. Tick sẵn / nhận được
// hay không là của MÁY CHỦ (`tick_san`, `nhan_duoc`): hướng dẫn tới phòng này,
// hoặc chưa hướng dẫn mà phòng này là phòng chuyên ★. Màn chỉ vẽ + gửi các id
// đang tick. Phải tick ≥1 mới gửi (máy chủ cũng chặn `CHUA_CHON_CHI_DINH`).
//
// Chỉ định đang chờ ở phòng khác mà được tick → máy chủ trả 409
// KHACH_O_PHONG_KHAC kèm câu; màn hỏi MỘT câu (không bắt lý do) rồi gửi lại
// `xac_nhan`. Dùng cho cả "Nhận vào phòng này" (Sắp đến) lẫn "Nhận thêm" (ô
// khách đã ở phòng).

import { useState } from "react";

import Button from "@/components/ui/Button";
import ChipChon from "@/components/ui/ChipChon";
import { type ThongBao } from "@/components/ui/ThongBaoHoanTac";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";

import { cauChiDinhPhong, guiThaoTac, type ChiDinhPhong } from "../../_lam-viec/api";
import { lenhHoanTac } from "../../_lam-viec/hoan-tac";

export default function NhanChiDinh({
  roomId,
  visitId,
  khach,
  chiDinh,
  bacSiLamId,
  nhanNut = "Nhận vào phòng này",
  onXong,
  onThoi,
  onBao,
}: {
  roomId: string;
  visitId: string;
  khach: string | null;
  chiDinh: ChiDinhPhong[];
  /** Phòng nhiều bác sĩ: bác sĩ đã chọn ("" = để máy chủ tự gán / giữ). */
  bacSiLamId?: string;
  nhanNut?: string;
  onXong: () => void;
  onThoi: () => void;
  onBao: (tb: ThongBao) => void;
}) {
  const duoc = chiDinh.filter((c) => c.nhan_duoc);
  const [tick, setTick] = useState<Set<string>>(() => new Set(duoc.filter((c) => c.tick_san).map((c) => c.id)));
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [hoi, setHoi] = useState<string | null>(null);

  const doi = (id: string) =>
    setTick((cu) => {
      const moi = new Set(cu);
      if (moi.has(id)) moi.delete(id);
      else moi.add(id);
      return moi;
    });

  const nhan = async (xacNhan: boolean) => {
    const ids = duoc.filter((c) => tick.has(c.id)).map((c) => c.id);
    if (ids.length === 0) return;
    setDang(true);
    setLoi(null);
    const kq = await guiThaoTac("nhan-vao-phong", visitId, {
      room_id: roomId,
      chi_dinh_ids: ids,
      ...(xacNhan ? { xac_nhan: true } : {}),
      ...(bacSiLamId ? { bac_si_lam_id: bacSiLamId } : {}),
    });
    setDang(false);
    if (!kq.ok) {
      if (kq.chiTiet?.ma === "KHACH_O_PHONG_KHAC") {
        setHoi(kq.loi);
        return;
      }
      setHoi(null);
      setLoi(kq.loi);
      return;
    }
    setHoi(null);
    const daNhan = Array.isArray(kq.data.da_nhan) ? (kq.data.da_nhan as string[]) : ids;
    const boQua = Array.isArray(kq.data.bo_qua) ? (kq.data.bo_qua as { ten: string; cau: string }[]) : [];
    onBao({
      cau:
        `Đã nhận ${daNhan.length} chỉ định của ${khach ?? "khách"} vào phòng` +
        (boQua.length ? ` · chưa nhận: ${boQua.map((b) => `${b.ten} (${b.cau})`).join(", ")}` : ""),
      goi: lenhHoanTac("hoan-tac-nhan", visitId, { room_id: roomId, chi_dinh_ids: daNhan }),
    });
    onXong();
  };

  const soTick = duoc.filter((c) => tick.has(c.id)).length;

  return (
    <div className="space-y-2 rounded-control border border-line bg-surface p-2">
      <p className="text-meta text-ink-muted">Tick chỉ định nhận vào phòng này:</p>
      <div className="flex flex-wrap gap-1.5">
        {duoc.map((c) => (
          <ChipChon key={c.id} chon={tick.has(c.id)} disabled={dang} onDoi={() => doi(c.id)}>
            <span className="min-w-0">
              {c.ten ?? "—"}
              {c.chuyen ? " ★" : ""}
              <span className="block text-meta text-ink-muted">
                {cauChiDinhPhong(c)}
                {c.chua_chot ? " · chưa chốt" : ""}
              </span>
            </span>
          </ChipChon>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="primary" disabled={dang || soTick === 0} onClick={() => void nhan(false)}>
          {dang ? "Đang nhận…" : soTick === 0 ? "Tick ít nhất một chỉ định" : `${nhanNut} (${soTick})`}
        </Button>
        <Button type="button" size="sm" variant="ghost" disabled={dang} onClick={onThoi}>
          Thôi
        </Button>
      </div>
      {hoi ? (
        <XacNhanTaiCho
          cau={hoi}
          nhanDongY="Nhận sang phòng này"
          dangGui={dang}
          onDongY={() => void nhan(true)}
          onThoi={() => setHoi(null)}
        />
      ) : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
