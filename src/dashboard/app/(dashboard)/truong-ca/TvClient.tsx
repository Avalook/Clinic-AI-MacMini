"use client";

// Màn TV PHÒNG CHỜ — chỉ số thứ tự, không tên, không dịch vụ.

import type { DispatchPatient, DispatchRoom } from "./types";
import { LiveBadge, ReadFailed, useDispatchLive } from "./shared";

export default function TvClient({
  initial,
}: {
  initial: { patients: DispatchPatient[]; rooms: DispatchRoom[]; ok: boolean };
}) {
  const live = useDispatchLive({ ...initial, alerts: [] });
  return (
    <div className="dispatch-scope">
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10 }}>
        <LiveBadge seconds={live.staleSeconds} ok={live.ok} />
      </div>
      <ReadFailed ok={live.ok} />
      <TvBoard rooms={live.rooms} patients={live.patients} />
    </div>
  );
}

function TvBoard({
  rooms,
  patients,
}: {
  rooms: DispatchRoom[];
  patients: DispatchPatient[];
}) {
  const shown = rooms.filter((r) => r.show_on_tv);
  return (
    <div>
      <div
        style={{ fontSize: 12, color: "var(--ink-muted)", marginBottom: 10 }}
      >
        Màn hình công cộng: chỉ hiện <b>số thứ tự</b>, không hiện tên bệnh nhân
        hay dịch vụ.
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 12,
        }}
      >
        {shown.map((r) => {
          const queue = patients
            .filter((p) => p.room_code === r.code && p.queue_number)
            .sort((a, b) => b.wait_minutes - a.wait_minutes)
            .map((p) => p.queue_number);
          return (
            <div key={r.id} className="card" style={{ padding: 14 }}>
              <div
                style={{
                  fontWeight: 800,
                  fontSize: 13,
                  letterSpacing: 0.4,
                  textTransform: "uppercase",
                  marginBottom: 10,
                }}
              >
                {r.name}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink-muted)" }}>
                Đang phục vụ
              </div>
              <div style={{ fontSize: 34, fontWeight: 800, lineHeight: 1.1 }}>
                {queue[0] ?? "—"}
              </div>
              <div
                style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 8 }}
              >
                Tiếp theo
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {queue.slice(1, 7).map((n) => (
                  <span key={n} className="badge badge-neutral">
                    {n}
                  </span>
                ))}
                {queue.length <= 1 && (
                  <span style={{ fontSize: 12, color: "var(--ink-faint)" }}>—</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
