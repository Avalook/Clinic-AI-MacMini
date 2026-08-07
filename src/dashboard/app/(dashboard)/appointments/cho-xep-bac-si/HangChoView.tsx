"use client";

// Hàng chờ xếp bác sĩ — mỗi dòng là một lịch khách đã hẹn nhưng chưa có người khám.
//
// Việc của quản lý ở màn này là DUY NHẤT: chọn bác sĩ rồi bấm xếp. Không đổi
// giờ, không huỷ — hai việc ấy đã có màn riêng và cần lý do riêng.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarClock, UserPlus, TriangleAlert } from "lucide-react";
import { fmtDateTimeOrDate } from "../../../../lib/datetime";

export interface DongCho {
  id: string;
  slot_start: string;
  status: string;
  notes: string | null;
  benh_nhan: string | null;
  patient_code: string | null;
  phone_primary: string | null;
  dich_vu: string | null;
  tuan_da_chot: boolean;
}

export interface BacSi {
  id: string;
  label: string;
}

export default function HangChoView({
  rows,
  doctors,
}: {
  rows: DongCho[];
  doctors: BacSi[];
}) {
  const router = useRouter();
  const [chon, setChon] = useState<Record<string, string>>({});
  const [dangXep, setDangXep] = useState<string | null>(null);
  const [loi, setLoi] = useState<Record<string, string>>({});

  async function xep(id: string) {
    const bacSi = chon[id];
    if (!bacSi) {
      setLoi((c) => ({ ...c, [id]: "Chọn bác sĩ trước." }));
      return;
    }
    setDangXep(id);
    setLoi((c) => ({ ...c, [id]: "" }));
    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, action: "assign_doctor", doctor_id: bacSi }),
    });
    setDangXep(null);
    if (!res.ok) {
      const chiTiet = await res
        .json()
        .then((d: { error?: string }) => d.error)
        .catch(() => null);
      // Câu hay gặp nhất ở đây là "Khung giờ đã đầy" — trần số chỗ áp đúng lúc
      // gán người. Hiện nguyên văn để quản lý biết phải chọn bác sĩ khác.
      setLoi((c) => ({
        ...c,
        [id]: chiTiet ?? `Không xếp được (lỗi ${res.status}).`,
      }));
      return;
    }
    router.refresh();
  }

  if (rows.length === 0) {
    return (
      <p className="rounded-card bg-success-bg px-4 py-3 text-sm text-success">
        Không còn lịch nào chờ xếp bác sĩ.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-card bg-surface shadow-card">
      <ul className="divide-y divide-line-soft">
        {rows.map((r) => (
          <li key={r.id} className="grid gap-2 px-4 py-3 lg:grid-cols-[1.4fr_1fr_auto] lg:items-center">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-ink">
                {r.benh_nhan ?? "Chưa có tên"}
                {r.phone_primary && (
                  <span className="ml-2 font-mono text-xs font-normal text-ink-muted">
                    {r.phone_primary}
                  </span>
                )}
              </p>
              <p className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
                <span className="inline-flex items-center gap-1">
                  <CalendarClock className="size-3.5" aria-hidden="true" />
                  {fmtDateTimeOrDate(r.slot_start)}
                </span>
                <span>{r.dich_vu ?? "Chưa chọn dịch vụ"}</span>
                {r.patient_code && (
                  <span className="font-mono">{r.patient_code}</span>
                )}
              </p>
              {/* Xếp bác sĩ cho một tuần chưa chốt là xếp dựa trên bản nháp —
                  lịch trực tuần đó còn đổi được. Nói ra chứ đừng chặn. */}
              {!r.tuan_da_chot && (
                <p className="mt-1 inline-flex items-center gap-1 rounded-chip bg-warning-bg px-2 py-0.5 text-[11px] text-warning">
                  <TriangleAlert className="size-3" aria-hidden="true" />
                  Tuần này chưa áp dụng lịch trực
                </p>
              )}
              {r.notes && (
                <p className="mt-1 line-clamp-2 text-xs text-ink-soft">{r.notes}</p>
              )}
            </div>

            <select
              value={chon[r.id] ?? ""}
              onChange={(e) => setChon((c) => ({ ...c, [r.id]: e.target.value }))}
              className="h-9 w-full rounded-control border border-line bg-surface px-2 text-sm text-ink outline-none focus:border-brand-600"
            >
              <option value="">— Chọn bác sĩ —</option>
              {doctors.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.label}
                </option>
              ))}
            </select>

            <div className="flex flex-col items-start gap-1">
              <button
                type="button"
                onClick={() => xep(r.id)}
                disabled={dangXep === r.id}
                className="inline-flex items-center gap-1.5 rounded-control bg-brand-600 px-3 py-2 text-sm font-medium text-surface transition-colors hover:bg-brand-700 disabled:opacity-50"
              >
                <UserPlus className="size-4" aria-hidden="true" />
                {dangXep === r.id ? "Đang xếp…" : "Xếp bác sĩ"}
              </button>
              {loi[r.id] && (
                <span className="max-w-64 text-xs text-danger">{loi[r.id]}</span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
