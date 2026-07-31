"use client";

// Danh sách đợt khám chờ xác nhận (PENDING_CLOSE) + 2 nút cho CSKH:
//   "Xác nhận đóng" → PATCH close   ·   "Còn theo dõi" → PATCH reopen
// Sau thao tác refresh route để bảng tự rớt dòng đã xử lý.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { fmtDate } from "../../../lib/datetime";

export interface EpisodeRow {
  id: string;
  opened_at: string;
  last_visit_at: string | null;
  patient_name: string;
  patient_code: string | null;
  service_name: string;
}

export default function EpisodesBoard({ rows }: { rows: EpisodeRow[] }) {
  const router = useRouter();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(id: string, action: "close" | "reopen") {
    setBusyId(id);
    setError(null);
    const res = await fetch("/api/episodes", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, action }),
    });
    setBusyId(null);
    if (!res.ok) {
      setError((await res.json()).error ?? "Có lỗi xảy ra.");
      return;
    }
    router.refresh();
  }

  if (rows.length === 0) {
    return (
      <p className="rounded-lg border border-line bg-white px-4 py-6 text-center text-sm text-ink-muted">
        Không có đợt khám nào đang chờ xác nhận. 🎉
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {error && (
        <p className="rounded bg-danger-bg px-3 py-2 text-sm text-danger">{error}</p>
      )}
      <ul className="space-y-2">
        {rows.map((r) => (
          <li
            key={r.id}
            className="flex flex-col gap-3 rounded-lg border border-brand-100 bg-white p-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <p className="font-medium text-ink">
                {r.patient_name}
                {r.patient_code && (
                  <span className="ml-2 text-xs text-ink-faint">{r.patient_code}</span>
                )}
              </p>
              <p className="text-sm text-ink-soft">
                {r.service_name}
                {" · "}
                <span className="text-ink-muted">
                  lượt gần nhất{" "}
                  {r.last_visit_at ? fmtDate(r.last_visit_at) : fmtDate(r.opened_at)}
                </span>
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              <button
                onClick={() => act(r.id, "close")}
                disabled={busyId === r.id}
                className="min-h-9 rounded-lg bg-brand-600 px-3 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
              >
                Xác nhận đóng
              </button>
              <button
                onClick={() => act(r.id, "reopen")}
                disabled={busyId === r.id}
                className="min-h-9 rounded-lg border border-line bg-white px-3 text-sm text-ink-soft hover:bg-surface-sunken disabled:opacity-50"
              >
                Còn theo dõi
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
