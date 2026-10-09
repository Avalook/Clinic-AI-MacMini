"use client";

// DẢI LIỆU TRÌNH CỦA MỘT CHỈ ĐỊNH, tự nạp — cho màn KHÔNG có `KhoiDieuTri` (phòng
// dịch vụ, Tuyền 09/10/2026: bác sĩ trực ở phòng lập / chọn lộ trình ngay đó,
// không phải quay về bàn khám). CÙNG `DaiLieuTrinh` với bàn khám → hai màn cùng
// số, cùng nút; nghe bảng liệu trình nên bên kia bấm là bên này đổi.
// Chỉ định không phải điều trị → máy chủ không trả nó trong `chi_dinh` → không vẽ.
// Ai sửa được do máy chủ nói (`ghi_duoc`).

import { useCallback, useEffect, useState } from "react";

import { docLT, type LieuTrinhLuot } from "@/lib/lieu-trinh";
import { useNgheBang } from "../../dung-nghe-bang";
import { DaiLieuTrinh } from "./LieuTrinhThe";

export default function LieuTrinhChiDinh({ visitId, orderId }: { visitId: string; orderId: string }) {
  const [lt, setLt] = useState<LieuTrinhLuot | null>(null);
  const nap = useCallback(() => {
    void docLT<LieuTrinhLuot>("theo-luot", visitId).then((d) => {
      if (d) setLt(d);
    });
  }, [visitId]);
  useEffect(() => {
    let huy = false;
    void docLT<LieuTrinhLuot>("theo-luot", visitId).then((d) => {
      if (!huy) setLt(d);
    });
    return () => {
      huy = true;
    };
  }, [visitId]);
  useNgheBang(["lieu_trinh", "lieu_trinh_buoi", "lieu_trinh_lich_su", "lieu_trinh_tra_truoc", "service_order"], nap);

  const cd = lt?.chi_dinh.find((c) => c.order_id === orderId);
  if (!lt || !cd) return null;
  return (
    <section aria-label="Lộ trình điều trị" className="space-y-2 border-t border-line pt-3">
      <DaiLieuTrinh visitId={visitId} cd={cd} luot={lt} choGhi={lt.ghi_duoc !== false} onDoi={nap} />
    </section>
  );
}
