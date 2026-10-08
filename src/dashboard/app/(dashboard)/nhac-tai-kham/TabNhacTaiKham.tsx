"use client";

// Hai tab của màn gọi khách hằng ngày (08/10/2026): "Nhắc tái khám" (hàng đợi
// gọi nhắc như cũ) · "Liệu trình" (đề xuất chưa đăng ký / đang dở). Tab ẩn bằng
// class, không gỡ khỏi cây — ghi chú cuộc gọi đang gõ dở không mất khi đổi tab.
// `?tab=lieu-trinh` mở thẳng tab Liệu trình.

import { useState, type ReactNode } from "react";

import ThanhTab from "@/components/ui/ThanhTab";

export type TabNhac = "nhac" | "lieu-trinh";

export default function TabNhacTaiKham({
  tabDau,
  nhac,
  lieuTrinh,
}: {
  tabDau: TabNhac;
  nhac: ReactNode;
  lieuTrinh: ReactNode;
}) {
  const [tab, setTab] = useState<TabNhac>(tabDau);
  return (
    <div className="space-y-4">
      <ThanhTab
        nhan="Việc gọi khách"
        muc={[
          { ma: "nhac", nhan: "Nhắc tái khám" },
          { ma: "lieu-trinh", nhan: "Liệu trình" },
        ]}
        chon={tab}
        onChon={setTab}
      />
      <div className={tab === "nhac" ? "" : "hidden"}>{nhac}</div>
      <div className={tab === "lieu-trinh" ? "" : "hidden"}>{lieuTrinh}</div>
    </div>
  );
}
