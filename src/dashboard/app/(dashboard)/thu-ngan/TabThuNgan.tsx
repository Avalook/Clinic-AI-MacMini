"use client";

// Lịch sử theo ca đã trực tách khỏi quầy đang làm để xem lại không cấp quyền thu tiền.
import { useState } from "react";

import ThanhNgay from "@/components/ui/ThanhNgay";
import { ngayNgan } from "@/lib/thanh-ngay";

import { useNgayXem } from "../_lam-viec/dung-ngay-xem";
import GiaoDich from "./GiaoDich";
import LichSuThu from "./LichSuThu";
import QuayThuNgan from "./QuayThuNgan";
import NgayTruc, { useNgayTruc } from "./NgayTruc";

const TAB = [
  { ma: "cho", nhan: "Chờ thanh toán" },
  { ma: "hom_nay", nhan: "Đã thanh toán hôm nay" },
  { ma: "lich_su", nhan: "Lịch sử giao dịch" },
] as const;

export default function TabThuNgan({ quay, chiXem = false }: { quay: "dich_vu" | "thuoc"; chiXem?: boolean }) {
  const [tab, setTab] = useState<(typeof TAB)[number]["ma"]>("cho");
  const { ngay, homNay, chonNgay } = useNgayXem();
  const phamVi = useNgayTruc(quay, ngay);
  const ngayXem = phamVi.ngayXem ?? ngay;
  const laHomNay = ngayXem === homNay;
  const khoa = `${ngayXem}:${phamVi.ca ?? ""}:${phamVi.coSo ?? ""}`;
  const thaoTac = !chiXem && phamVi.thaoTac && laHomNay;
  const tabXem = tab === "cho" && !thaoTac ? "lich_su" : tab;
  const [coSoDangTruc, setCoSoDangTruc] = useState("");
  const activeCoSoIds = [...new Set(phamVi.dangTruc.map(d => d.co_so_id))];
  const activeCoSo = activeCoSoIds.includes(coSoDangTruc) ? coSoDangTruc : activeCoSoIds[0];
  return (
    <div className="flex flex-col gap-3">
      {phamVi.ds?.quan_ly ? <ThanhNgay
        motNgay
        nhan="Xem quầy thu theo ngày"
        khoang={{ tu: ngay, den: ngay }}
        homNay={homNay}
        soNgaySau={0}
        onChon={(k) => chonNgay(k?.den ?? homNay)}
      /> : <NgayTruc state={phamVi} onChon={chonNgay} />}
      <div role="tablist" aria-label="Quầy thu ngân" className="flex flex-wrap gap-1">
        {TAB.filter(t => t.ma !== "cho" || thaoTac).map((t) => (
          <button
            key={t.ma}
            type="button"
            role="tab"
            aria-selected={tabXem === t.ma}
            onClick={() => setTab(t.ma)}
            className={`min-h-10 rounded-control px-3 text-sm font-medium ${
              tabXem === t.ma ? "bg-brand-600 text-white" : "bg-surface-muted text-ink-soft hover:bg-surface-sunken"
            }`}
          >
            {t.ma === "hom_nay" && !laHomNay ? `Đã thanh toán ngày ${ngayNgan(ngayXem)}` : t.nhan}
          </button>
        ))}
      </div>
      {tabXem === "cho" && activeCoSoIds.length > 1 ? <select aria-label="Cơ sở đang trực" value={activeCoSo} onChange={e => setCoSoDangTruc(e.target.value)} className="min-h-10 rounded-control bg-surface px-3 ring-1 ring-line-strong">
        {activeCoSoIds.map((id, i) => <option key={id} value={id}>{phamVi.ds?.items.flatMap(d => d.co_so ?? []).find(c => c.id === id)?.ten ?? `Cơ sở trực ${i + 1}`}</option>)}
      </select> : null}
      {phamVi.ready && (tabXem === "cho" ? (
        <QuayThuNgan key={`${khoa}:${activeCoSo ?? ""}`} quay={quay} ngay={homNay} coSo={activeCoSo} />
      ) : tabXem === "lich_su" ? (
        <LichSuThu key={khoa} quay={quay} ngay={ngayXem} ca={phamVi.ca} coSo={phamVi.coSo} restricted={phamVi.restricted} thaoTac={thaoTac} />
      ) : (
        <GiaoDich key={`${tabXem}:${khoa}`} lichSu={false} quay={quay} ngay={ngayXem} ca={phamVi.ca} coSo={phamVi.coSo} restricted={phamVi.restricted} thaoTac={thaoTac} />
      ))}
    </div>
  );
}
