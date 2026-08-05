"use client";

// DisplayBoard — Màn hình TV phòng chờ (image_15 + 2 ảnh V2).
// Hiển thị số đang gọi theo khu vực. KHÔNG hiện tên bệnh nhân (riêng tư).
// Tự refresh mỗi 30s.

import { useEffect, useState } from "react";
import { VN_TZ } from "../../lib/datetime";

interface DisplayDoctor {
  full_name: string | null;
}

interface DisplayService {
  name: string | null;
}

interface DisplayAppt {
  id: string;
  slot_start: string;
  status: string;
  queue_number: string | null;
  booking_channel: string | null;
  doctor: DisplayDoctor | null;
  service: DisplayService | null;
}

interface Props {
  appts: DisplayAppt[];
}

const ZONES = [
  { key: "kham", label: "Khám bác sĩ", prefix: "C" },
  { key: "sa1", label: "SA1", prefix: "SA" },
  { key: "sa2", label: "SA2", prefix: "SA" },
  { key: "sa3", label: "SA3", prefix: "SA" },
  { key: "xn", label: "Xét nghiệm", prefix: "X" },
  { key: "tt", label: "Thanh toán", prefix: "T" },
] as const;

function zoneOf(a: DisplayAppt): string {
  const svc = (a.service?.name ?? "").toLowerCase();
  if (svc.includes("siêu âm") || svc.includes("sieu am")) {
    return "sa";
  }
  if (svc.includes("xét nghiệm") || svc.includes("xet nghiem")) return "xn";
  return "kham";
}

export default function DisplayBoard({ appts }: Props) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);

  // Số đang gọi = lịch CHECKED_IN / IN_PROGRESS gần nhất theo giờ
  const called = appts
    .filter((a) => a.status === "CHECKED_IN" || a.status === "IN_PROGRESS")
    .sort((a, b) => +new Date(a.slot_start) - +new Date(b.slot_start));

  const byZone = (zone: string) =>
    called.filter((a) => zoneOf(a).startsWith(zone));

  const timeStr = now.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: VN_TZ,
  });
  const dateStr = now.toLocaleDateString("vi-VN", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: VN_TZ,
  });

  return (
    <div className="flex h-screen flex-col bg-ink text-white">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-white/10 px-8 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-500 text-lg font-bold">
            C
          </div>
          <div>
            <div className="text-lg font-semibold">ClinicAI</div>
            <div className="text-xs text-white/60">CONNECTED CLINIC WORKFLOW</div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold tabular-nums">{timeStr}</div>
          <div className="text-sm text-white/60">{dateStr}</div>
        </div>
      </header>

      {/* Main: 6 khu */}
      <main className="grid flex-1 grid-cols-3 gap-4 p-6 lg:grid-cols-6">
        {ZONES.map((z) => {
          const rows = byZone(z.key);
          const current = rows[0] ?? null;
          const next = rows.slice(1, 4);
          return (
            <section
              key={z.key}
              className="flex flex-col rounded-2xl border border-white/10 bg-white/5 p-4"
            >
              <h2 className="text-sm font-semibold uppercase tracking-wide text-white/60">
                {z.label}
              </h2>
              <div className="mt-3 flex flex-1 flex-col items-center justify-center">
                {current ? (
                  <>
                    <div className="text-5xl font-bold tabular-nums text-brand-300">
                      {current.queue_number ?? "—"}
                    </div>
                    <div className="mt-1 text-xs text-white/60">ĐANG GỌI</div>
                  </>
                ) : (
                  <div className="text-3xl font-bold text-white/20">—</div>
                )}
              </div>
              <div className="mt-3 border-t border-white/10 pt-2">
                <div className="text-[11px] text-white/40">Tiếp theo</div>
                <div className="mt-1 space-y-0.5">
                  {next.length === 0 ? (
                    <div className="text-xs text-white/30">—</div>
                  ) : (
                    next.map((a) => (
                      <div
                        key={a.id}
                        className="text-sm font-medium tabular-nums text-white/70"
                      >
                        {a.queue_number ?? "—"}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </section>
          );
        })}
      </main>

      {/* Footer */}
      <footer className="flex items-center justify-between border-t border-white/10 px-8 py-3 text-sm text-white/50">
        <div>Vui lòng chờ đến lượt số của mình</div>
        <div>WiFi: Dr4Women · Hotline: 1900 0000</div>
      </footer>
    </div>
  );
}