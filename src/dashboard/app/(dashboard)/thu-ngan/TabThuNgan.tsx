"use client";

// Ba tab của quầy thu ngân (batch pilot 18/09/2026): Chờ thanh toán · Đã thanh
// toán hôm nay · Lịch sử giao dịch. Tab đầu là quầy thu sẵn có (QuayThuNgan),
// hai tab sau chỉ đọc.

import { useState } from "react";

import GiaoDich from "./GiaoDich";
import QuayThuNgan from "./QuayThuNgan";

const TAB = [
  { ma: "cho", nhan: "Chờ thanh toán" },
  { ma: "hom_nay", nhan: "Đã thanh toán hôm nay" },
  { ma: "lich_su", nhan: "Lịch sử giao dịch" },
] as const;

export default function TabThuNgan({ quay }: { quay: "dich_vu" | "thuoc" }) {
  const [tab, setTab] = useState<(typeof TAB)[number]["ma"]>("cho");
  return (
    <div className="flex flex-col gap-3">
      <div role="tablist" aria-label="Quầy thu ngân" className="flex flex-wrap gap-1">
        {TAB.map((t) => (
          <button
            key={t.ma}
            type="button"
            role="tab"
            aria-selected={tab === t.ma}
            onClick={() => setTab(t.ma)}
            className={`min-h-10 rounded-control px-3 text-sm font-medium ${
              tab === t.ma ? "bg-brand-600 text-white" : "bg-surface-muted text-ink-soft hover:bg-surface-sunken"
            }`}
          >
            {t.nhan}
          </button>
        ))}
      </div>
      {tab === "cho" ? <QuayThuNgan quay={quay} /> : <GiaoDich key={tab} lichSu={tab === "lich_su"} />}
    </div>
  );
}
