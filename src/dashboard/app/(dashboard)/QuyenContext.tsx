"use client";

// QUYỀN CỦA NGƯỜI ĐANG ĐĂNG NHẬP, cho mọi component client trong khung
// (27/09/2026, đợt 3). `Shell` nhận `quyen` từ layout (một lời gọi
// `/phan-quyen/toi` mỗi lượt dựng trang) và phát lại ở đây — không lời gọi
// mạng nào thêm, không truyền prop qua ba tầng component.
//
// Luật hỏi quyền nằm ở `lib/quyen-client.ts` (hàm thuần, có bài kiểm).

import { createContext, useContext } from "react";

import { checkOutDuoc, coQuyen } from "@/lib/quyen-client";
import { canCheckin, type ClinicRole } from "@/lib/roles";

const QuyenContext = createContext<readonly string[] | null>(null);

export const QuyenProvider = QuyenContext.Provider;

/** Danh sách capability, hoặc `null` khi máy chủ chưa trả lời. */
export function useQuyen(): readonly string[] | null {
  return useContext(QuyenContext);
}

/** Tài khoản này được bấm Check-out (đóng lượt) không. */
export function useCheckOutDuoc(): boolean {
  return checkOutDuoc(useQuyen());
}

/** Được CHECK-IN (kênh "Trực tiếp" hôm nay tự check-in) — theo LEGO Tiếp đón
 *  (`reception.checkin.perform`), không theo vai (mở full lego 30/09/2026).
 *  Máy chủ chưa trả lời quyền → rơi về vai như trước. Máy chủ vẫn tự kiểm
 *  (`booking_service.create` → `doi_quyen`). */
export function useCheckInDuoc(role: ClinicRole | null | undefined): boolean {
  const quyen = useQuyen();
  return quyen === null
    ? canCheckin(role ?? null)
    : coQuyen(quyen, "reception.checkin.perform");
}
