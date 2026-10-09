"use client";

// Bộ lọc CHUNG của màn Tiếp đón (09/10/2026): thanh tìm + tab trên cùng
// (`ThanhLocTiepDon`, trong `ManTiepDon`) phát; bảng Lịch hẹn và danh sách tiếp
// đón đọc. Ngoài màn Tiếp đón (vd /home) không có bên phát → null → không lọc.
//
// Context thay vì props: để `reception/queue/page.tsx` vẫn tự vẽ (import thẳng)
// hai bảng dữ liệu — bản đồ code (`scripts/ban-do-code.py`) đi theo import từ
// trang, thêm một tầng bọc là mất API/service của màn khỏi bản đồ.

import { createContext, useContext } from "react";

import type { LocTiepDon } from "./tiep-don";

export const LocTiepDonContext = createContext<LocTiepDon | null>(null);

export function useLocTiepDon(): LocTiepDon | null {
  return useContext(LocTiepDonContext);
}
