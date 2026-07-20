"use client";

// Top-right toast for reception / CSKH / management: lists appointments a
// doctor declined (DOCTOR_DECLINED) so they can be re-assigned. Dismissible with
// the ✕ for the current session; it reappears on reload while any remain.

import { useState } from "react";

export interface DeclinedItem {
  id: string;
  patientName: string;
  time: string;
  doctorName: string;
}

export default function DeclinedNotice({ items }: { items: DeclinedItem[] }) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed || items.length === 0) return null;

  return (
    <div className="fixed inset-x-3 top-14 z-20 rounded-lg border border-[#fecaca] bg-white p-3 shadow-[0_4px_12px_rgba(0,0,0,0.12)] sm:inset-x-auto sm:right-16 sm:top-4 sm:z-50 sm:w-80">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-[#dc2626]">
          🔔 {items.length} lịch bị bác sĩ từ chối
        </p>
        <button
          onClick={() => setDismissed(true)}
          aria-label="Tắt thông báo"
          className="-mt-0.5 text-base leading-none text-[#a1a1aa] hover:text-[#71717a]"
        >
          ✕
        </button>
      </div>
      <p className="mt-0.5 text-xs text-[#71717a]">Cần phân lại bác sĩ.</p>
      <ul className="mt-2 space-y-1">
        {items.slice(0, 5).map((it) => (
          <li key={it.id} className="text-xs text-[#4d4d4d]">
            <span className="font-medium text-[#171717]">{it.patientName}</span>
            {" · "}
            {it.time}
            {" · "}
            <span className="text-[#888888]">BS {it.doctorName}</span>
          </li>
        ))}
        {items.length > 5 && (
          <li className="text-xs text-[#888888]">+{items.length - 5} lịch khác…</li>
        )}
      </ul>
    </div>
  );
}
