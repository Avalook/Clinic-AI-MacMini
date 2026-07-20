"use client";

// Danh sách BN QUÁ HẠN tái khám / không phản hồi, chia bucket theo số ngày quá hạn.
// Mỗi dòng có nút "Đã gọi" → ghi nhật ký CSKH (POST /api/cskh-followup) rồi refetch.
// THUẦN trình bày + 1 action ghi log — KHÔNG đụng visit/lâm sàng.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { fmtDate } from "../../../lib/datetime";

export interface FollowupRow {
  clinic_patient_id: string;
  full_name: string;
  phone_primary: string | null;
  ngay: string; // tai_kham.ngay (anchor) — ngày tái khám bác sĩ dặn
  overdue_days: number;
}

export interface FollowupBucket {
  tier: number; // ngưỡng (>= tier ngày quá hạn)
  label: string;
  rows: FollowupRow[];
}

const TIER_STYLE: Record<number, string> = {
  2: "bg-[#fef9c3] text-[#a16207]",
  10: "bg-[#fed7aa] text-[#c2410c]",
  20: "bg-[#fecaca] text-[#dc2626]",
  30: "bg-[#fee2e2] text-[#b91c1c]",
};

export default function CskhFollowupList({ buckets }: { buckets: FollowupBucket[] }) {
  const router = useRouter();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [calledIds, setCalledIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const total = buckets.reduce((n, b) => n + b.rows.length, 0);

  async function markCalled(clinicPatientId: string) {
    if (busyId) return;
    setBusyId(clinicPatientId);
    setError(null);
    const res = await fetch("/api/cskh-followup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clinic_patient_id: clinicPatientId }),
    });
    setBusyId(null);
    if (!res.ok) {
      setError((await res.json().catch(() => ({}))).error ?? "Lỗi ghi nhật ký CSKH.");
      return;
    }
    setCalledIds((s) => new Set(s).add(clinicPatientId));
    router.refresh(); // BN có lịch mới / log mới → cập nhật danh sách
  }

  if (total === 0) {
    return (
      <div className="rounded-lg border border-[#e4e4e7] bg-white px-4 py-6 text-center text-sm text-[#888888]">
        Không có BN quá hạn tái khám cần nhắc gọi.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-md bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">{error}</div>
      )}
      {buckets
        .filter((b) => b.rows.length > 0)
        .map((b) => (
          <div key={b.tier}>
            <div className="mb-1.5 flex items-center gap-2">
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${TIER_STYLE[b.tier] ?? "bg-[#f4f4f5] text-[#52525b]"}`}
              >
                {b.label}
              </span>
              <span className="text-xs text-[#888888]">{b.rows.length} BN</span>
            </div>
            <ul className="divide-y divide-[#e4e4e7] rounded-lg border border-[#e4e4e7] bg-white">
              {b.rows.map((r) => {
                const called = calledIds.has(r.clinic_patient_id);
                return (
                  <li
                    key={r.clinic_patient_id}
                    className="flex items-center gap-3 px-4 py-2.5"
                  >
                    <span className="w-24 shrink-0 text-sm font-semibold text-[#171717]">
                      {fmtDate(r.ngay)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-[#171717]">
                        {r.full_name}
                        <span className="ml-2 font-normal text-[#888888]">
                          {r.phone_primary ?? "— chưa có SĐT"}
                        </span>
                      </p>
                      <p className="truncate text-xs text-[#dc2626]">
                        Quá hạn {r.overdue_days} ngày
                      </p>
                    </div>
                    <button
                      onClick={() => markCalled(r.clinic_patient_id)}
                      disabled={busyId === r.clinic_patient_id || called}
                      className={
                        "shrink-0 rounded-md border px-2.5 py-1 text-xs font-medium disabled:opacity-60 " +
                        (called
                          ? "border-[#bbf7d0] bg-[#f0fdf4] text-[#15803d]"
                          : "border-[#f3cfe0] text-[#9d2463] hover:bg-[#fdf2f8]")
                      }
                    >
                      {busyId === r.clinic_patient_id
                        ? "..."
                        : called
                          ? "✓ Đã ghi"
                          : "Đã gọi"}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
    </div>
  );
}
