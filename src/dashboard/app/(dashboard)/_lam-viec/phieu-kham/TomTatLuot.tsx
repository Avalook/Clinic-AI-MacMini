"use client";

// Tóm tắt lượt (trạng thái · đã chờ/đã khám · từ lúc check-in · nút Bắt đầu…)
// vẽ TRONG thẻ khách thay vì một ô riêng phía trên (Tuyền 27/09/2026 tối:
// "phần ở trên tóm tắt xuống ô dưới cho gọn").
//
// Bàn khám dựng nội dung (nó giữ state và lệnh), thẻ khách chỉ đặt vào chỗ.
// `baoHien` cho Bàn khám biết thẻ khách đã hiện — chưa hiện (phiếu chưa tải,
// lỗi tải) thì Bàn khám vẫn vẽ ô cũ để nút [Bắt đầu] không bao giờ mất.

import { createContext, useContext, useEffect, type ReactNode } from "react";

export interface TomTatLuotGiaTri {
  noiDung: ReactNode;
  baoHien: (hien: boolean) => void;
}

export const TomTatLuotContext = createContext<TomTatLuotGiaTri | null>(null);

/** Thẻ khách gọi: trả nội dung tóm tắt (nếu có) và tự báo "đã hiện". */
export function useTomTatLuot(): ReactNode {
  const gt = useContext(TomTatLuotContext);
  const baoHien = gt?.baoHien;
  useEffect(() => {
    if (!baoHien) return;
    baoHien(true);
    return () => baoHien(false);
  }, [baoHien]);
  return gt?.noiDung ?? null;
}
