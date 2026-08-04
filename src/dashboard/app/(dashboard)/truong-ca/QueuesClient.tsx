"use client";

// Màn HÀNG ĐỢI THEO TRẠM — ai đang chờ ở phòng nào, chờ bao lâu.

import type { DispatchPatient, DispatchRoom } from "./types";
import { LiveBadge, ReadFailed, useDispatchLive } from "./shared";

export default function QueuesClient({
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
      <Queues rooms={live.rooms} patients={live.patients} />
    </div>
  );
}

function Queues({
  rooms,
  patients,
}: {
  rooms: DispatchRoom[];
  patients: DispatchPatient[];
}) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
        gap: 12,
      }}
    >
      {rooms.map((r) => {
        const here = patients
          .filter((p) => p.room_code === r.code)
          .sort((a, b) => b.wait_minutes - a.wait_minutes);
        return (
          <div key={r.id} className="card" style={{ padding: 12 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>
              {r.name}{" "}
              <span style={{ fontWeight: 400, color: "var(--ink-muted)" }}>
                {r.floor ? `· tầng ${r.floor} ` : ""}· {here.length} người
              </span>
              {/* Chưa khai tầng thì NÓI RA, đừng im. Im lặng làm người ta tưởng
                  phòng này cùng tầng với phòng đang đứng. */}
              {!r.floor && (
                <span
                  style={{
                    fontWeight: 400,
                    fontSize: 11,
                    color: "var(--warning)",
                  }}
                >
                  {" "}· chưa khai tầng
                </span>
              )}
            </div>
            {here.length === 0 ? (
              <div style={{ fontSize: 12, color: "var(--ink-faint)" }}>
                Không có ai đang chờ
              </div>
            ) : (
              here.map((p) => (
                <div
                  key={p.visit_id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 12,
                    padding: "5px 0",
                    borderBottom: "1px solid var(--line)",
                  }}
                >
                  <span>
                    {p.queue_number ? `${p.queue_number} · ` : ""}
                    {p.patient_name}
                  </span>
                  <span
                    style={{
                      color:
                        p.wait_minutes > p.threshold_minutes
                          ? "var(--danger)"
                          : "var(--ink-muted)",
                    }}
                  >
                    {p.wait_minutes}′
                  </span>
                </div>
              ))
            )}
          </div>
        );
      })}
    </div>
  );
}
