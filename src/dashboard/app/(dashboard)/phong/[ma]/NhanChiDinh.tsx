"use client";

// NÚT NHẬN THEO CHỈ ĐỊNH (Tuyền chốt 07/10/2026 tối — bỏ tick sẵn, bỏ hộp tick).
//
// Một nút gửi ĐÚNG các id nó mang: [Nhận] trên dòng một chỉ định = một id;
// [Nhận cả N] = mọi chỉ định nhận được của khách. Nhận được hay không là của
// MÁY CHỦ (`nhan_duoc`); ★ / hướng dẫn chỉ là nhãn.
//
// Chỉ định đang chờ ở phòng khác (hoặc khách đang làm ở phòng khác) → máy chủ
// trả 409 KHACH_O_PHONG_KHAC kèm câu; nút hỏi MỘT câu (không bắt lý do) rồi gửi
// lại `xac_nhan`. Sau khi nhận: thông báo kèm Hoàn tác đúng các chỉ định vừa nhận.

import { useState } from "react";

import Button, { type ButtonVariant } from "@/components/ui/Button";
import { type ThongBao } from "@/components/ui/ThongBaoHoanTac";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";

import { guiThaoTac } from "../../_lam-viec/api";
import { lenhHoanTac } from "../../_lam-viec/hoan-tac";

export default function NhanChiDinh({
  roomId,
  visitId,
  khach,
  ids,
  nhan = "Nhận",
  variant = "primary",
  bacSiLamId,
  onXong,
  onBao,
}: {
  roomId: string;
  visitId: string;
  khach: string | null;
  /** Các chỉ định nút này nhận (máy chủ đã nói `nhan_duoc`). */
  ids: string[];
  nhan?: string;
  variant?: ButtonVariant;
  /** Phòng nhiều bác sĩ: bác sĩ đã chọn ("" = để máy chủ tự gán / giữ). */
  bacSiLamId?: string;
  onXong: () => void;
  onBao: (tb: ThongBao) => void;
}) {
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [hoi, setHoi] = useState<string | null>(null);

  const gui = async (xacNhan: boolean) => {
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

  return (
    <>
      <Button type="button" size="sm" variant={variant} disabled={dang || ids.length === 0} onClick={() => void gui(false)}>
        {dang ? "Đang nhận…" : nhan}
      </Button>
      {hoi ? (
        <div className="basis-full">
          <XacNhanTaiCho
            cau={hoi}
            nhanDongY="Nhận sang phòng này"
            dangGui={dang}
            onDongY={() => void gui(true)}
            onThoi={() => setHoi(null)}
          />
        </div>
      ) : null}
      {loi ? (
        <p role="alert" className="basis-full text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </>
  );
}
