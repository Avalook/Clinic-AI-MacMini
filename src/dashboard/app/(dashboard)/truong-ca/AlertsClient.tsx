"use client";

// Màn CẢNH BÁO & NGƯỠNG — xếp theo mức độ, và chỗ chỉnh ngưỡng từng phòng.

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { DispatchAlert, DispatchPatient, DispatchRoom } from "./types";
import NutGoiBoPhan from "./NutGoiBoPhan";
import {
  type ActFn,
  LiveBadge,
  ReadFailed,
  Toast,
  useDispatchAction,
  useDispatchLive,
} from "./shared";

export default function AlertsClient({
  initial,
}: {
  initial: {
    patients: DispatchPatient[];
    rooms: DispatchRoom[];
    alerts: DispatchAlert[];
    ok: boolean;
  };
}) {
  const live = useDispatchLive(initial);
  const { act, toast } = useDispatchAction();
  return (
    <div className="dispatch-scope">
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10 }}>
        <LiveBadge seconds={live.staleSeconds} ok={live.ok} />
      </div>
      <ReadFailed ok={live.ok} />
      <Alerts alerts={live.alerts} rooms={live.rooms} onAct={act} />
      <Toast text={toast} />
    </div>
  );
}

function Alerts({
  alerts,
  rooms,
  onAct,
}: {
  alerts: DispatchAlert[];
  rooms: DispatchRoom[];
  onAct: ActFn;
}) {
  const [edit, setEdit] = useState<Record<string, { w: number; n: number }>>({});
  return (
    <div>
      {alerts.length === 0 ? (
        <div className="card" style={{ padding: 20, textAlign: "center" }}>
          <div style={{ fontWeight: 700 }}>Không có cảnh báo</div>
          <div style={{ fontSize: 12, color: "var(--ink-muted)" }}>
            Mọi trạm đang trong ngưỡng.
          </div>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {alerts.map((a, i) => (
            <div
              key={i}
              className="card"
              style={{
                padding: 12,
                borderLeft: `3px solid ${
                  a.severity === "critical" ? "var(--danger)" : "var(--warning)"
                }`,
              }}
            >
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <AlertTriangle
                  size={14}
                  color={
                    a.severity === "critical" ? "var(--danger)" : "var(--warning)"
                  }
                />
                <span style={{ fontWeight: 600, fontSize: 13 }}>{a.message}</span>
              </div>
              {/* NỬA CÒN THIẾU: nói được với ai. Xem NutGoiBoPhan.tsx. */}
              <NutGoiBoPhan
                tieuDe={a.message}
                noiDung={
                  a.patients.length > 0
                    ? `Bệnh nhân: ${a.patients.map((p) => p.name).join(" · ")}`
                    : a.message
                }
                nguonId={a.room_code ?? a.type}
                khan={a.severity === "critical"}
              />
              {/* "chỉ rõ phòng VÀ danh sách bệnh nhân bị ảnh hưởng" */}
              {a.patients.length > 0 && (
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--ink-muted)",
                    marginTop: 4,
                    marginLeft: 22,
                  }}
                >
                  {a.patients.map((p) => p.name).join(" · ")}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <h3 style={{ fontSize: 14, fontWeight: 700, margin: "20px 0 10px" }}>
        Ngưỡng cảnh báo theo phòng
      </h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Phòng</th>
              <th>Chờ quá (phút)</th>
              <th>Số người tối đa</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rooms.map((r) => {
              const e = edit[r.id] ?? {
                w: r.threshold_minutes,
                n: r.threshold_waiting,
              };
              return (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td>
                    <input
                      type="text"
                      value={e.w}
                      onChange={(ev) =>
                        setEdit({
                          ...edit,
                          [r.id]: { ...e, w: Number(ev.target.value) || 0 },
                        })
                      }
                      style={{ width: 70 }}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={e.n}
                      onChange={(ev) =>
                        setEdit({
                          ...edit,
                          [r.id]: { ...e, n: Number(ev.target.value) || 0 },
                        })
                      }
                      style={{ width: 70 }}
                    />
                  </td>
                  <td>
                    <button
                      className="btn btn-secondary"
                      onClick={() =>
                        onAct(
                          "threshold",
                          {
                            room_id: r.id,
                            wait_minutes: e.w,
                            max_waiting: e.n,
                          },
                          `✓ Đã lưu ngưỡng cho ${r.name}`,
                        )
                      }
                    >
                      Lưu
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
