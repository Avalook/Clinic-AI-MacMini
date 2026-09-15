"use client";

// DẤU KHÁCH ƯU TIÊN trên hồ sơ (Tuyền chốt 15/09/2026). Chỉ để lễ tân biết —
// không tự đổi thứ tự khám. Bật thì bắt buộc lý do; backend kiểm lại.

import { useState } from "react";

import PriorityChip from "@/components/ui/PriorityChip";

export default function DauUuTien({
  clinicPatientId,
  uuTien,
  lyDo,
  onDoi,
}: {
  clinicPatientId: string;
  uuTien: boolean;
  lyDo: string | null;
  onDoi: () => void;
}) {
  const [mo, setMo] = useState(false);
  const [nhap, setNhap] = useState(lyDo ?? "");
  const [dangGhi, setDangGhi] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  async function ghi(bat: boolean) {
    setDangGhi(true);
    setLoi(null);
    const res = await fetch(`/api/patients/${clinicPatientId}/uu-tien`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uu_tien: bat, ly_do: bat ? nhap : null }),
    });
    const json = await res.json().catch(() => ({}));
    setDangGhi(false);
    if (!res.ok) {
      setLoi(json.error ?? "Không lưu được.");
      return;
    }
    setMo(false);
    onDoi();
  }

  return (
    <div className="mt-2 space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        {uuTien ? (
          <>
            <PriorityChip priority="P0" />
            <span className="text-label text-ink-muted">{lyDo}</span>
            <button
              type="button"
              disabled={dangGhi}
              onClick={() => void ghi(false)}
              className="text-label text-ink-muted underline disabled:opacity-50"
            >
              Bỏ dấu
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setMo((v) => !v)}
            className="text-label text-brand-700 underline"
          >
            Đánh dấu khách ưu tiên
          </button>
        )}
      </div>
      {mo && !uuTien && (
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={nhap}
            onChange={(e) => setNhap(e.target.value)}
            maxLength={500}
            placeholder="Lý do ưu tiên (bắt buộc)"
            className="min-w-0 flex-1 rounded-control border border-line px-2 py-1 text-sm"
          />
          <button
            type="button"
            disabled={dangGhi || !nhap.trim()}
            onClick={() => void ghi(true)}
            className="rounded-control bg-brand-600 px-2 py-1 text-label font-semibold text-white disabled:opacity-50"
          >
            Lưu
          </button>
        </div>
      )}
      {loi && <p className="text-label text-danger">{loi}</p>}
    </div>
  );
}
