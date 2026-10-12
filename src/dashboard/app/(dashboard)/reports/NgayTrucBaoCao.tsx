"use client";

import type { ReportAccess } from "./access";

export type ReportCalendar = ReportAccess & {
  ngay_truc?: { ngay: string; co_so_theo_ca: Record<string, string[]> }[];
};

export default function NgayTrucBaoCao({ access, ngay, onChon }: {
  access?: ReportCalendar; ngay: string; onChon: (ngay: string) => void;
}) {
  const days = access?.ngay_truc ?? [];
  return <label className="w-full space-y-1 text-meta text-ink-muted sm:w-auto">
    Ngày trực
    <select aria-label="Ngày trực báo cáo" className="min-h-10 w-full rounded-control bg-surface px-3 ring-1 ring-line-strong"
      value={days.some(d => d.ngay === ngay) ? ngay : ""}
      onChange={e => { if (e.target.value) onChon(e.target.value); }}>
      <option value="" disabled>{days.length ? "Chọn ngày đã trực" : "Chưa có ngày trực được duyệt"}</option>
      {days.map(d => <option key={d.ngay} value={d.ngay}>{d.ngay.split("-").reverse().join("/")}</option>)}
    </select>
  </label>;
}
