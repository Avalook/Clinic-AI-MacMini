"use client";

// CSKH báo quản lý: lịch này đã hẹn giờ nhưng chưa có bác sĩ.
//
// Chỉ hiện khi lịch đại diện thật sự chưa có bác sĩ — nút luôn hiện là nút sẽ
// bị bấm nhầm, và mỗi lần bấm nhầm là một thông báo làm phiền quản lý.
//
// Bấm lại khi chưa ai xử lý thì KHÔNG tạo thông báo thứ hai (khoá theo lịch hẹn
// ở thong_bao). CSKH bấm lại vì sốt ruột là chuyện thường; nhân đôi thì không.

import { useState } from "react";
import { UserPlus, Check } from "lucide-react";

export default function BaoXepBacSi({
  appointmentId,
}: {
  appointmentId: string;
}) {
  const [dangGui, setDangGui] = useState(false);
  const [xong, setXong] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  async function bao() {
    setDangGui(true);
    setLoi(null);
    const res = await fetch("/api/appointments/cho-xep-bac-si", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ appointment_id: appointmentId }),
    });
    setDangGui(false);
    if (!res.ok) {
      const chiTiet = await res
        .json()
        .then((d: { error?: string }) => d.error)
        .catch(() => null);
      setLoi(chiTiet ?? `Không báo được (lỗi ${res.status}).`);
      return;
    }
    setXong(true);
  }

  if (xong) {
    return (
      <p className="flex items-center gap-1.5 rounded-xl bg-success-bg px-3 py-2 text-xs text-success">
        <Check className="size-3.5 shrink-0" aria-hidden="true" />
        Đã báo quản lý. Lịch nằm trong hàng chờ xếp bác sĩ.
      </p>
    );
  }

  return (
    <div className="space-y-1">
      <button
        type="button"
        onClick={bao}
        disabled={dangGui}
        className="w-full inline-flex items-center justify-center gap-1.5 rounded-xl border border-brand-600 bg-surface py-2 px-3 text-xs font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-50"
      >
        <UserPlus className="size-3.5" aria-hidden="true" />
        {dangGui ? "Đang báo…" : "Báo quản lý xếp bác sĩ"}
      </button>
      {loi && <p className="text-xs text-danger">{loi}</p>}
    </div>
  );
}
