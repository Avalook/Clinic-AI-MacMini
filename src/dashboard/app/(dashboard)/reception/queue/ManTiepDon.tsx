"use client";

// Thân màn Tiếp đón khách: thanh tìm + lọc TRÊN CÙNG (09/10/2026) giữ MỘT bộ
// lọc cho cả hai bảng bên dưới — "Lịch hẹn" (`WeeklyAppointmentsTable`, dùng
// chung với Trang chủ) và danh sách tiếp đón (`QueueBoard`). Hai bảng do trang
// (server) tự vẽ làm `children`; chúng đọc bộ lọc qua `LocTiepDonContext`.

import { useState, type ReactNode } from "react";

import { LocTiepDonContext } from "@/lib/loc-tiep-don-context";
import { LOC_MAC_DINH, type LocTiepDon } from "@/lib/tiep-don";

import ThanhLocTiepDon from "./ThanhLocTiepDon";

export default function ManTiepDon({
  dem,
  themKhachDuoc,
  children,
}: {
  /** Số đếm của danh sách tiếp đón hôm nay (máy chủ). null = không đọc được. */
  dem: { tat_ca: number; chua_den: number; da_den: number } | null;
  themKhachDuoc: boolean;
  children: ReactNode;
}) {
  const [loc, setLoc] = useState<LocTiepDon>(LOC_MAC_DINH);
  return (
    <LocTiepDonContext.Provider value={loc}>
      <ThanhLocTiepDon loc={loc} onDoi={setLoc} dem={dem} themKhachDuoc={themKhachDuoc} />
      {children}
    </LocTiepDonContext.Provider>
  );
}
