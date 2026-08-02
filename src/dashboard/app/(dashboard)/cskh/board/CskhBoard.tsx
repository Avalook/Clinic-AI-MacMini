"use client";

// CskhBoard — Không gian làm việc CSKH (image_1 + image_2 + image_10).
// 2 cột: lịch hẹn cần xác nhận (trái) + follow-up cần gọi (phải).
// Nút xử lý: Xác nhận lịch, Đã gọi, Đóng case.

import { useMemo, useState } from "react";

interface CskhPatient {
  full_name: string | null;
  phone_primary: string | null;
}

interface CskhDoctor {
  full_name: string | null;
}

interface CskhAppt {
  id: string;
  slot_start: string;
  status: string;
  queue_number: string | null;
  booking_channel: string | null;
  patient: CskhPatient | null;
  doctor: CskhDoctor | null;
}

interface CskhFollowup {
  id: string;
  action_type: string | null;
  note: string | null;
  status: string | null;
  created_at: string;
  patient: CskhPatient | null;
}

interface Props {
  appts: CskhAppt[];
  followups: CskhFollowup[];
}

const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });

export default function CskhBoard({ appts, followups }: Props) {
  const [search, setSearch] = useState("");
  const [doneAppts, setDoneAppts] = useState<Set<string>>(new Set());
  const [doneFus, setDoneFus] = useState<Set<string>>(new Set());

  const filteredAppts = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return appts;
    return appts.filter(
      (a) =>
        a.patient?.full_name?.toLowerCase().includes(q) ||
        a.patient?.phone_primary?.toLowerCase().includes(q),
    );
  }, [appts, search]);

  const pendingAppts = filteredAppts.filter((a) => !doneAppts.has(a.id));
  const pendingFus = followups.filter((f) => !doneFus.has(f.id));

  return (
    <div className="grid h-full grid-cols-2 gap-4 p-4">
      {/* Cột trái: lịch hẹn cần xác nhận */}
      <section className="flex flex-col rounded-control border border-line bg-surface">
        <div className="border-b border-line p-3">
          <h2 className="text-sm font-semibold text-ink">Lịch hẹn cần xác nhận</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            {pendingAppts.length} lịch chờ xử lý
          </p>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm tên / SĐT…"
            className="mt-2 w-full rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-sm text-ink outline-none focus:border-brand-500"
          />
        </div>
        <div className="flex-1 overflow-y-auto">
          {pendingAppts.length === 0 ? (
            <p className="p-4 text-sm text-ink-muted">Không có lịch chờ xác nhận.</p>
          ) : (
            pendingAppts.map((a) => (
              <div
                key={a.id}
                className="border-b border-line px-3 py-2.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-ink">
                    {a.patient?.full_name ?? "Chưa có tên"}
                  </span>
                  <span className="shrink-0 text-xs text-ink-faint">
                    {fmtTime(a.slot_start)}
                  </span>
                </div>
                <div className="mt-0.5 text-xs text-ink-muted">
                  {a.patient?.phone_primary ?? "—"} ·{" "}
                  {a.doctor?.full_name ?? "Chưa phân BS"}
                </div>
                <div className="mt-1.5 flex items-center gap-2">
                  <span className="rounded-full bg-warning-bg px-2 py-0.5 text-[11px] font-medium text-warning">
                    {a.status === "CSKH_CONFIRMED" ? "Đã xác nhận" : "Chờ xác nhận"}
                  </span>
                  <button
                    onClick={() =>
                      setDoneAppts((prev) => new Set(prev).add(a.id))
                    }
                    className="ml-auto rounded-control bg-brand-600 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-brand-700"
                  >
                    Xác nhận lịch
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      {/* Cột phải: follow-up cần gọi */}
      <section className="flex flex-col rounded-control border border-line bg-surface">
        <div className="border-b border-line p-3">
          <h2 className="text-sm font-semibold text-ink">Follow-up cần gọi</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            {pendingFus.length} việc chờ xử lý
          </p>
        </div>
        <div className="flex-1 overflow-y-auto">
          {pendingFus.length === 0 ? (
            <p className="p-4 text-sm text-ink-muted">Không có follow-up hôm nay.</p>
          ) : (
            pendingFus.map((f) => (
              <div key={f.id} className="border-b border-line px-3 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-ink">
                    {f.patient?.full_name ?? "Chưa có tên"}
                  </span>
                  <span className="shrink-0 text-xs text-ink-faint">
                    {fmtDate(f.created_at)}
                  </span>
                </div>
                <div className="mt-0.5 text-xs text-ink-muted">
                  {f.patient?.phone_primary ?? "—"} · {f.action_type ?? "Follow-up"}
                </div>
                {f.note && (
                  <div className="mt-1 truncate text-xs text-ink-soft">{f.note}</div>
                )}
                <div className="mt-1.5 flex items-center gap-2">
                  <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700">
                    {f.status ?? "MỞ"}
                  </span>
                  <button
                    onClick={() => setDoneFus((prev) => new Set(prev).add(f.id))}
                    className="ml-auto rounded-control bg-success px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-success/90"
                  >
                    Đã gọi
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}