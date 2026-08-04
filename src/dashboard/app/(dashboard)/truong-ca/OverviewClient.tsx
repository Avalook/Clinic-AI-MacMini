"use client";

// Màn TOÀN CẢNH — mỗi bệnh nhân một dòng, kèm panel chi tiết bên phải.

import { useMemo, useState } from "react";
import { Clock, Search, Users, X } from "lucide-react";
import type { DispatchPatient, DispatchRoom, RouteTemplate } from "./types";
import { humanMinutes, nodeLabel } from "./types";
import {
  type ActFn,
  type LiveData,
  LiveBadge,
  ReadFailed,
  roomWithFloor,
  Toast,
  useDispatchAction,
  useDispatchLive,
} from "./shared";

export default function OverviewClient({
  initial,
  routes,
}: {
  initial: { patients: DispatchPatient[]; rooms: DispatchRoom[]; ok: boolean };
  routes: RouteTemplate[];
}) {
  const live = useDispatchLive({ ...initial, alerts: [] });
  const { act, toast } = useDispatchAction();
  const [selected, setSelected] = useState<DispatchPatient | null>(null);

  return (
    <div className="dispatch-scope">
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10 }}>
        <LiveBadge seconds={live.staleSeconds} ok={live.ok} />
      </div>
      <ReadFailed ok={live.ok} />
      <Board live={live} routes={routes} selected={selected} onSelect={setSelected} onAct={act} />
      <Toast text={toast} />
    </div>
  );
}

function Board({
  live,
  routes,
  selected,
  onSelect,
  onAct,
}: {
  live: LiveData;
  routes: RouteTemplate[];
  selected: DispatchPatient | null;
  onSelect: (p: DispatchPatient | null) => void;
  onAct: ActFn;
}) {
  const [q, setQ] = useState("");
  const [room, setRoom] = useState("all");
  const [doctor, setDoctor] = useState("all");

  const doctors = useMemo(
    () =>
      [...new Set(live.patients.map((p) => p.doctor_name).filter(Boolean))].sort(),
    [live.patients],
  );

  const rows = useMemo(() => {
    let out = live.patients;
    const s = q.trim().toLowerCase();
    if (s)
      out = out.filter(
        (p) =>
          (p.patient_name ?? "").toLowerCase().includes(s) ||
          (p.patient_code ?? "").toLowerCase().includes(s),
      );
    if (room !== "all") out = out.filter((p) => p.room_code === room);
    if (doctor !== "all") out = out.filter((p) => p.doctor_name === doctor);
    // Chờ lâu nhất lên đầu — đó là thứ Trưởng ca cần xử lý trước.
    return [...out].sort((a, b) => b.wait_minutes - a.wait_minutes);
  }, [live.patients, q, room, doctor]);

  return (
    <div style={{ display: "flex", gap: 16 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <StationCards rooms={live.rooms} />

        <div
          style={{
            display: "flex",
            gap: 8,
            margin: "16px 0 12px",
            flexWrap: "wrap",
          }}
        >
          <div style={{ position: "relative", flex: "0 0 240px" }}>
            <Search
              size={14}
              style={{
                position: "absolute",
                left: 10,
                top: "50%",
                transform: "translateY(-50%)",
                color: "var(--ink-muted)",
              }}
            />
            <input
              type="search"
              placeholder="Tìm tên hoặc mã bệnh nhân…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              style={{ width: "100%", paddingLeft: 30 }}
            />
          </div>
          <select value={room} onChange={(e) => setRoom(e.target.value)}>
            <option value="all">Mọi phòng</option>
            {live.rooms.map((r) => (
              <option key={r.code} value={r.code}>
                {roomWithFloor(r.name, r.floor)}
              </option>
            ))}
          </select>
          {/* Lọc theo bác sĩ — prototype thiếu, mà đây là bộ lọc Notion nêu đầu tiên. */}
          <select value={doctor} onChange={(e) => setDoctor(e.target.value)}>
            <option value="all">Mọi bác sĩ</option>
            {doctors.map((d) => (
              <option key={d} value={d ?? ""}>
                {d}
              </option>
            ))}
          </select>
          <span
            style={{
              alignSelf: "center",
              fontSize: 12,
              color: "var(--ink-muted)",
            }}
          >
            {rows.length} bệnh nhân
          </span>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Bệnh nhân</th>
                <th>Chuyên khoa</th>
                <th>Đang ở</th>
                <th>Chờ</th>
                <th>Tổng</th>
                <th>Đã xong</th>
                <th>Kế tiếp</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ color: "var(--ink-muted)" }}>
                    Không có bệnh nhân nào đang trong phòng khám.
                  </td>
                </tr>
              )}
              {rows.map((p) => {
                const over = p.wait_minutes > p.threshold_minutes;
                return (
                  <tr
                    key={p.visit_id}
                    onClick={() => onSelect(p)}
                    className={selected?.visit_id === p.visit_id ? "selected" : ""}
                    style={{ cursor: "pointer" }}
                  >
                    <td>
                      <div style={{ fontWeight: 600 }}>{p.patient_name ?? "—"}</div>
                      <div style={{ fontSize: 11, color: "var(--ink-muted)" }}>
                        {p.patient_code ?? ""}
                        {p.queue_number ? ` · số ${p.queue_number}` : ""}
                      </div>
                    </td>
                    <td>{p.specialty ?? "—"}</td>
                    <td>
                      {p.room_name
                        ? roomWithFloor(p.room_name, p.room_floor)
                        : nodeLabel(p.current_node_code)}
                      {p.doctor_name && (
                        <div style={{ fontSize: 11, color: "var(--ink-muted)" }}>
                          {p.doctor_name}
                        </div>
                      )}
                    </td>
                    <td>
                      <span
                        className={over ? "badge badge-danger" : "badge badge-neutral"}
                      >
                        {p.wait_minutes}′
                      </span>
                    </td>
                    {/* Tổng thời gian trong phòng khám — prototype không có cột này. */}
                    <td style={{ color: "var(--ink-muted)" }}>
                      {humanMinutes(p.total_minutes)}
                    </td>
                    <td style={{ fontSize: 11, color: "var(--ink-muted)" }}>
                      {p.done_steps.length
                        ? p.done_steps.map(nodeLabel).join(" · ")
                        : "—"}
                    </td>
                    <td>
                      {p.next_step ? (
                        nodeLabel(p.next_step)
                      ) : (
                        <span className="badge badge-warning">Chưa có tuyến</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <DetailPanel
          patient={
            live.patients.find((p) => p.visit_id === selected.visit_id) ?? selected
          }
          rooms={live.rooms}
          routes={routes}
          onClose={() => onSelect(null)}
          onAct={onAct}
        />
      )}
    </div>
  );
}

function StationCards({ rooms }: { rooms: DispatchRoom[] }) {
  const tone = {
    ok: { bg: "var(--success-bg)", fg: "var(--success)", label: "Trong mức" },
    warning: { bg: "var(--warning-bg)", fg: "var(--warning)", label: "Cần chú ý" },
    critical: { bg: "var(--danger-bg)", fg: "var(--danger)", label: "Quá tải" },
  };
  return (
    <div
      className="fade-in"
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
        gap: 10,
      }}
    >
      {rooms.map((r) => {
        const t = tone[r.state];
        return (
          <div key={r.id} className="card" style={{ padding: 12 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 8,
              }}
            >
              <span style={{ fontWeight: 700, fontSize: 13 }}>{r.name}</span>
              <span
                className="badge"
                style={{ background: t.bg, color: t.fg }}
              >
                {t.label}
              </span>
            </div>
            <div style={{ display: "flex", gap: 14, fontSize: 12 }}>
              <span>
                <Users size={12} /> đang khám <b>{r.serving}</b>
              </span>
              <span>
                <Clock size={12} /> chờ <b>{r.waiting}</b>
              </span>
            </div>
            <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 6 }}>
              lâu nhất {r.max_wait}′ · TB {r.avg_wait}′ · ngưỡng{" "}
              {r.threshold_minutes}′/{r.threshold_waiting} người
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DetailPanel({
  patient,
  rooms,
  routes,
  onClose,
  onAct,
}: {
  patient: DispatchPatient;
  rooms: DispatchRoom[];
  routes: RouteTemplate[];
  onClose: () => void;
  onAct: ActFn;
}) {
  const [reason, setReason] = useState("");
  const [targetRoom, setTargetRoom] = useState("");
  const [routeCode, setRouteCode] = useState("");
  const [isException, setIsException] = useState(false);
  const [busy, setBusy] = useState(false);

  // Chỉ những phòng phục vụ ĐÚNG bước hiện tại mới chuyển sang được — backend
  // cũng từ chối, nhưng hiện sẵn danh sách đúng thì không ai phải thử rồi lỗi.
  //
  // Đọc `serves_nodes`, KHÔNG đọc `node_code`. Một phòng khám phục vụ cả năm
  // chuyên khoa; lọc theo bước chính (đang là KHAM-PHUKHOA cho cả bốn phòng)
  // thì một ca Nam khoa sẽ thấy danh sách rỗng và Trưởng ca không chuyển được
  // đi đâu cả.
  const sameStepRooms = rooms.filter(
    (r) =>
      r.serves_nodes.includes(patient.current_node_code ?? "") &&
      r.id !== patient.room_id,
  );

  async function transfer() {
    if (!targetRoom || !reason.trim()) return;
    setBusy(true);
    const ok = await onAct(
      "transfer-room",
      {
        visit_id: patient.visit_id,
        node_code: patient.current_node_code,
        room_id: targetRoom,
        reason: reason.trim(),
      },
      // Câu này Trưởng ca đọc lên cho bệnh nhân. "Đã chuyển phòng" không chỉ
      // được đường; "lên tầng 4, phòng SA3" thì chỉ được.
      `✓ Đã chuyển: ${roomWithFloor(
        rooms.find((r) => r.id === targetRoom)?.name ?? null,
        rooms.find((r) => r.id === targetRoom)?.floor ?? null,
      )}`,
    );
    setBusy(false);
    if (ok) {
      setReason("");
      setTargetRoom("");
    }
  }

  async function applyRoute() {
    if (!routeCode) return;
    if (isException && !reason.trim()) return;
    setBusy(true);
    const ok = await onAct(
      "route",
      {
        visit_id: patient.visit_id,
        template_code: routeCode,
        is_exception: isException,
        reason: reason.trim() || null,
      },
      "✓ Đã áp dụng tuyến điều phối",
    );
    setBusy(false);
    if (ok) setReason("");
  }

  return (
    <aside
      className="card slide-in-right"
      style={{ flex: "0 0 320px", padding: 16, alignSelf: "flex-start" }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <div style={{ fontWeight: 700 }}>{patient.patient_name}</div>
          <div style={{ fontSize: 11, color: "var(--ink-muted)" }}>
            {patient.patient_code} · trong phòng khám{" "}
            {humanMinutes(patient.total_minutes)}
          </div>
        </div>
        <button onClick={onClose} className="btn btn-ghost" style={{ padding: 4 }}>
          <X size={16} />
        </button>
      </div>

      <div style={{ margin: "14px 0 6px", fontSize: 12, fontWeight: 700 }}>
        Hành trình
      </div>
      <ol style={{ margin: 0, paddingLeft: 16, fontSize: 12, lineHeight: 1.9 }}>
        {patient.done_steps.map((s) => (
          <li key={s} style={{ color: "var(--ink-muted)" }}>
            {nodeLabel(s)} <span style={{ color: "var(--success)" }}>✓</span>
          </li>
        ))}
        <li style={{ fontWeight: 700 }}>
          {nodeLabel(patient.current_node_code)}
          {patient.room_name
            ? ` · ${roomWithFloor(patient.room_name, patient.room_floor)}`
            : ""}{" "}
          — đang chờ{" "}
          {patient.wait_minutes}′
        </li>
        {patient.next_step && (
          <li style={{ color: "var(--ink-faint)" }}>{nodeLabel(patient.next_step)}</li>
        )}
      </ol>

      <div style={{ margin: "14px 0 6px", fontSize: 12, fontWeight: 700 }}>
        Lý do điều phối <span style={{ color: "var(--danger)" }}>*</span>
      </div>
      <input
        type="text"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="VD: SA1 quá tải, chuyển sang SA2"
        style={{ width: "100%" }}
      />

      {sameStepRooms.length > 0 && (
        <>
          <div style={{ margin: "12px 0 6px", fontSize: 12, fontWeight: 700 }}>
            Chuyển phòng
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <select
              value={targetRoom}
              onChange={(e) => setTargetRoom(e.target.value)}
              style={{ flex: 1 }}
            >
              <option value="">-- Chọn phòng --</option>
              {sameStepRooms.map((r) => (
                <option key={r.id} value={r.id}>
                  {roomWithFloor(r.name, r.floor)} (chờ {r.waiting})
                  {r.floor && patient.room_floor && r.floor !== patient.room_floor
                    ? " ↕"
                    : ""}
                </option>
              ))}
            </select>
            <button
              className="btn btn-primary"
              disabled={busy || !targetRoom || !reason.trim()}
              onClick={transfer}
            >
              Chuyển
            </button>
          </div>
        </>
      )}

      <div style={{ margin: "12px 0 6px", fontSize: 12, fontWeight: 700 }}>
        Tuyến điều phối
      </div>
      <select
        value={routeCode}
        onChange={(e) => setRouteCode(e.target.value)}
        style={{ width: "100%" }}
      >
        <option value="">-- Chọn tuyến --</option>
        {routes.map((r) => (
          <option key={r.code} value={r.code}>
            {r.name}
          </option>
        ))}
      </select>
      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 12,
          margin: "8px 0",
        }}
      >
        <input
          type="checkbox"
          checked={isException}
          onChange={() => setIsException(!isException)}
        />
        Đổi tuyến giữa chừng (bắt buộc ghi lý do)
      </label>
      {/* Bước đã hoàn tất không bị đụng tới — backend giữ chúng trong
          `kept_steps`. Nói ra để người bấm biết mình không làm mất gì. */}
      {patient.done_steps.length > 0 && (
        <div style={{ fontSize: 11, color: "var(--ink-muted)", marginBottom: 8 }}>
          Giữ nguyên bước đã xong: {patient.done_steps.map(nodeLabel).join(", ")}
        </div>
      )}
      <button
        className="btn btn-primary"
        style={{ width: "100%" }}
        disabled={busy || !routeCode || (isException && !reason.trim())}
        onClick={applyRoute}
      >
        Áp dụng tuyến
      </button>
    </aside>
  );
}
