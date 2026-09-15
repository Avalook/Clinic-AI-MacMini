"use client";

// Vẽ khung báo dưới tên khách — nội dung do `dungKhungBao` (khung-bao.ts) dựng.

import { AlertTriangle, BellRing, ChevronRight } from "lucide-react";
import type { DongBao } from "./khung-bao";

export default function KhungBao({
  dong,
  onSuaLich,
  onChonViec,
}: {
  dong: DongBao[];
  onSuaLich?: () => void;
  onChonViec?: (ma: string) => void;
}) {
  if (dong.length === 0) return null;
  return (
    <ul aria-label="Thay đổi ảnh hưởng lịch của khách" className="mt-2 space-y-1.5">
      {dong.map((d) => {
        const bam =
          d.hanhDong?.loai === "sua_lich"
            ? onSuaLich
            : d.hanhDong?.loai === "chon_viec" && onChonViec
              ? () => onChonViec((d.hanhDong as { ma: string }).ma)
              : undefined;
        const lop = `flex w-full items-start gap-2 rounded-control px-2 py-1.5 text-left text-label font-medium ${
          d.muc === "gap" ? "bg-warning-bg text-warning" : "bg-brand-50 text-brand-800"
        }`;
        const Icon = d.muc === "gap" ? AlertTriangle : BellRing;
        const noiDung = (
          <>
            <Icon className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            <span className="min-w-0 flex-1 leading-snug">{d.cau}</span>
            {bam && <ChevronRight className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />}
          </>
        );
        return (
          <li key={d.khoa}>
            {bam ? (
              <button type="button" onClick={bam} className={`${lop} hover:brightness-95`}>
                {noiDung}
              </button>
            ) : (
              <div className={lop}>{noiDung}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
