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
  2: "bg-warning-bg text-warning",
  10: "bg-warning-bg text-warning",
  20: "bg-danger-bg text-danger",
  30: "bg-danger-bg text-danger",
};

/**
 * The one existing follow-up mutation, shared by the full list and the V2
 * workspace detail panel. It only records an already-made call; it does not
 * alter appointments or clinical information.
 */
export function FollowupMarkButton({ patientId }: { patientId: string }) {
  const router = useRouter();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [calledIds, setCalledIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

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

  const called = calledIds.has(patientId);
  return (
    <div className="space-y-2">
      {error && (
        <div className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">
          {error}
        </div>
      )}
      <button
        type="button"
        onClick={() => markCalled(patientId)}
        disabled={busyId === patientId || called}
        className={
          "flex min-h-10 w-full items-center justify-center rounded-control px-3 text-sm font-semibold disabled:opacity-60 " +
          (called
            ? "bg-success-bg text-success"
            : "bg-brand-600 text-white hover:bg-brand-700")
        }
      >
        {busyId === patientId ? "Đang ghi…" : called ? "Đã ghi nhật ký cuộc gọi" : "Đã gọi"}
      </button>
    </div>
  );
}

export default function CskhFollowupList({ buckets }: { buckets: FollowupBucket[] }) {
  const total = buckets.reduce((n, b) => n + b.rows.length, 0);

  if (total === 0) {
    return (
      <div className="rounded-card border border-line bg-surface px-4 py-6 text-center text-sm text-ink-muted">
        Không có BN quá hạn tái khám cần nhắc gọi.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {buckets
        .filter((b) => b.rows.length > 0)
        .map((b) => (
          <div key={b.tier}>
            <div className="mb-1.5 flex items-center gap-2">
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${TIER_STYLE[b.tier] ?? "bg-surface-sunken text-ink-soft"}`}
              >
                {b.label}
              </span>
              <span className="text-xs text-ink-muted">{b.rows.length} BN</span>
            </div>
            <ul className="divide-y divide-line rounded-card border border-line bg-surface">
              {b.rows.map((r) => {
                return (
                  <li
                    key={r.clinic_patient_id}
                    className="flex items-center gap-3 px-4 py-2.5"
                  >
                    <span className="w-24 shrink-0 text-sm font-semibold text-ink">
                      {fmtDate(r.ngay)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-ink">
                        {r.full_name}
                        <span className="ml-2 font-normal text-ink-muted">
                          {r.phone_primary ?? "— chưa có SĐT"}
                        </span>
                      </p>
                      <p className="truncate text-xs text-danger">
                        Quá hạn {r.overdue_days} ngày
                      </p>
                    </div>
                    <div className="w-28 shrink-0">
                      <FollowupMarkButton patientId={r.clinic_patient_id} />
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
    </div>
  );
}
