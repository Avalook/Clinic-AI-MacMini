"use client";

// Ba tab của quầy thu ngân (batch pilot 18/09/2026): Chờ thanh toán · Đã thanh
// toán hôm nay · Lịch sử giao dịch. Tab đầu là quầy thu sẵn có (QuayThuNgan),
// hai tab sau chỉ đọc.
//
// THANH NGÀY (02/10/2026, Tuyền: "xem lại một ngày cũ để đối soát"): MỘT thanh
// chọn ngày (`components/ui/ThanhNgay`, chế độ một ngày — dùng chung với phòng
// dịch vụ / Bàn khám) cho cả ba tab. Ngày nằm trên URL (`?ngay=`) nên F5 / gửi
// link vẫn đúng ngày. Ngày cũ vẫn THU ĐƯỢC cho khách chưa trả — không khoá.

import { useState } from "react";

import ThanhNgay from "@/components/ui/ThanhNgay";
import { ngayNgan } from "@/lib/thanh-ngay";

import { useNgayXem } from "../_lam-viec/dung-ngay-xem";
import GiaoDich from "./GiaoDich";
import LichSuThu from "./LichSuThu";
import QuayThuNgan from "./QuayThuNgan";

const TAB = [
  { ma: "cho", nhan: "Chờ thanh toán" },
  { ma: "hom_nay", nhan: "Đã thanh toán hôm nay" },
  { ma: "lich_su", nhan: "Lịch sử giao dịch" },
] as const;

export default function TabThuNgan({ quay }: { quay: "dich_vu" | "thuoc" }) {
  const [tab, setTab] = useState<(typeof TAB)[number]["ma"]>("cho");
  const { ngay, homNay, laHomNay, chonNgay } = useNgayXem();
  return (
    <div className="flex flex-col gap-3">
      <ThanhNgay
        motNgay
        nhan="Xem quầy thu theo ngày"
        khoang={{ tu: ngay, den: ngay }}
        homNay={homNay}
        soNgaySau={0}
        onChon={(k) => chonNgay(k?.den ?? homNay)}
      />
      {!laHomNay ? (
        <p className="rounded-control border border-warning bg-warning-bg px-3 py-2 text-body text-warning">
          Đang xem ngày {ngayNgan(ngay)} — khách chưa trả của ngày này vẫn thu được
          như hôm nay; tiền thu ghi giờ thật lúc bấm.
        </p>
      ) : null}
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
            {t.ma === "hom_nay" && !laHomNay ? `Đã thanh toán ngày ${ngayNgan(ngay)}` : t.nhan}
          </button>
        ))}
      </div>
      {tab === "cho" ? (
        <QuayThuNgan quay={quay} ngay={ngay} />
      ) : tab === "lich_su" && quay === "dich_vu" ? (
        // Quầy dịch vụ (27/09, đợt 3): lịch sử gom theo khách + CSV + phiếu thu.
        <LichSuThu key={ngay} ngay={ngay} />
      ) : (
        <GiaoDich key={`${tab}:${ngay}`} lichSu={tab === "lich_su"} quay={quay} ngay={ngay} />
      )}
    </div>
  );
}
