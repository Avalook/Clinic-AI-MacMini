"use client";

// Hai góc nhìn của "Lịch làm việc chính thức" (27/09/2026 đợt 3, A9): theo vị
// trí (bảng Excel) và theo người. Cả hai do server dựng sẵn; ở đây chỉ bật/tắt
// bằng class, không gỡ khỏi cây — đổi tab không phải dựng lại bảng.

import { useState, type ReactNode } from "react";

import ThanhTab from "../../../components/ui/ThanhTab";

type Tab = "vi_tri" | "nguoi";

const MUC = [
  { ma: "vi_tri", nhan: "Theo vị trí" },
  { ma: "nguoi", nhan: "Theo người" },
] as const;

export default function TabLichLamViec({
  theoViTri,
  theoNguoi,
}: {
  theoViTri: ReactNode;
  theoNguoi: ReactNode;
}) {
  const [tab, setTab] = useState<Tab>("vi_tri");
  return (
    <div className="space-y-3">
      <ThanhTab muc={MUC} chon={tab} onChon={setTab} nhan="Góc nhìn lịch làm việc" />
      <div role="tabpanel" className={tab === "vi_tri" ? "" : "hidden"}>
        {theoViTri}
      </div>
      <div role="tabpanel" className={tab === "nguoi" ? "" : "hidden"}>
        {theoNguoi}
      </div>
    </div>
  );
}
